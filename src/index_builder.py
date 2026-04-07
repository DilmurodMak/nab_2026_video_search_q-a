"""
index_builder.py

Creates the nab-video-segments AI Search index and pushes one or more final
output files with embeddings.

Run after `python main.py` or `python src/build_all_final_outputs.py` has
produced `<video_name>_final_output.json` files.

Usage:
    python src/index_builder.py
    python src/index_builder.py \
        --input video_index/flight_simulator_final_output.json
    python src/index_builder.py --recreate-index
"""

import argparse
from collections.abc import Iterator, Sequence
import json
import os
from pathlib import Path
import sys
from typing import Any

try:
    from dotenv import load_dotenv
    from openai import AzureOpenAI
    from azure.identity import (
        DefaultAzureCredential,
        get_bearer_token_provider,
    )
    from azure.search.documents import SearchClient
    from azure.search.documents.indexes import SearchIndexClient
    from azure.search.documents.indexes.models import (
        HnswAlgorithmConfiguration,
        SearchField,
        SearchFieldDataType,
        SearchIndex,
        SearchableField,
        SemanticConfiguration,
        SemanticField,
        SemanticPrioritizedFields,
        SemanticSearch,
        SimpleField,
        VectorSearch,
        VectorSearchProfile,
    )
    from azure.core.credentials import AzureKeyCredential
except ModuleNotFoundError as exc:
    raise SystemExit(
        "Missing Python dependencies for index upload. "
        "Use '.venv/bin/python' or install the Azure SDK packages first."
    ) from exc


SRC_DIR = Path(__file__).resolve().parent

load_dotenv(SRC_DIR / ".env")

SEARCH_ENDPOINT = os.getenv("AZURE_SEARCH_ENDPOINT")
SEARCH_KEY = os.getenv("AZURE_SEARCH_API_KEY")
INDEX_NAME = os.getenv("AZURE_SEARCH_INDEX_NAME", "nab-video-segments")
OPENAI_ENDPOINT = os.getenv("AZURE_OPENAI_ENDPOINT")
EMBEDDING_MODEL = os.getenv(
    "AZURE_OPENAI_EMBEDDING_DEPLOYMENT",
    "text-embedding-3-large",
)
UPLOAD_BATCH_SIZE = 100

KNOWN_EMBEDDING_DIMENSIONS = {
    "text-embedding-3-large": 3072,
    "text-embedding-3-small": 1536,
}


def resolve_vector_dimensions() -> int:
    """Resolve vector dimensions from env or known embedding deployments."""
    configured_dimensions = os.getenv("AZURE_OPENAI_EMBEDDING_DIMENSIONS")
    if configured_dimensions:
        try:
            return int(configured_dimensions)
        except ValueError as exc:
            raise SystemExit(
                "ERROR: AZURE_OPENAI_EMBEDDING_DIMENSIONS must be an integer."
            ) from exc

    if EMBEDDING_MODEL in KNOWN_EMBEDDING_DIMENSIONS:
        return KNOWN_EMBEDDING_DIMENSIONS[EMBEDDING_MODEL]

    raise SystemExit(
        "ERROR: Unknown embedding deployment dimensions. "
        "Set AZURE_OPENAI_EMBEDDING_DIMENSIONS in src/.env."
    )


VECTOR_DIMENSIONS = resolve_vector_dimensions()


def check_env() -> None:
    """Validate the environment required for embeddings and index upload."""
    required_env_vars = [
        "AZURE_SEARCH_ENDPOINT",
        "AZURE_SEARCH_API_KEY",
        "AZURE_OPENAI_ENDPOINT",
    ]
    missing = [name for name in required_env_vars if not os.getenv(name)]
    if missing:
        print(f"ERROR: Missing .env values: {', '.join(missing)}")
        sys.exit(1)


def get_embedding(client: AzureOpenAI, text: str) -> list[float]:
    """Generate an embedding for one search document."""
    response = client.embeddings.create(input=text, model=EMBEDDING_MODEL)
    return response.data[0].embedding


def create_index(
    index_client: SearchIndexClient,
    recreate: bool = False,
) -> None:
    """Create or update the Azure AI Search index definition."""
    if recreate:
        try:
            index_client.delete_index(INDEX_NAME)
            print(f"Deleted existing index: {INDEX_NAME}")
        except Exception:
            pass

    fields = [
        SimpleField(
            name="id",
            type=SearchFieldDataType.String,
            key=True,
            filterable=True,
        ),
        SearchableField(
            name="videoName",
            type=SearchFieldDataType.String,
            filterable=True,
        ),
        SimpleField(
            name="sceneId",
            type=SearchFieldDataType.String,
            retrievable=True,
        ),
        SimpleField(
            name="startTimeMs",
            type=SearchFieldDataType.Int32,
            retrievable=True,
            filterable=True,
            sortable=True,
        ),
        SimpleField(
            name="endTimeMs",
            type=SearchFieldDataType.Int32,
            retrievable=True,
        ),
        SearchableField(name="description", type=SearchFieldDataType.String),
        SearchableField(name="transcript", type=SearchFieldDataType.String),
        SearchableField(name="searchText", type=SearchFieldDataType.String),
        SearchField(
            name="speakers",
            type=SearchFieldDataType.Collection(SearchFieldDataType.String),
            searchable=True,
            filterable=True,
        ),
        SearchField(
            name="ocrText",
            type=SearchFieldDataType.Collection(SearchFieldDataType.String),
            searchable=True,
            filterable=True,
        ),
        SearchField(
            name="labels",
            type=SearchFieldDataType.Collection(SearchFieldDataType.String),
            searchable=True,
            filterable=True,
        ),
        SearchField(
            name="brands",
            type=SearchFieldDataType.Collection(SearchFieldDataType.String),
            searchable=True,
            filterable=True,
        ),
        SearchField(
            name="locations",
            type=SearchFieldDataType.Collection(SearchFieldDataType.String),
            searchable=True,
            filterable=True,
        ),
        SearchField(
            name="objects",
            type=SearchFieldDataType.Collection(SearchFieldDataType.String),
            searchable=True,
            filterable=True,
        ),
        SearchField(
            name="topics",
            type=SearchFieldDataType.Collection(SearchFieldDataType.String),
            searchable=True,
            filterable=True,
        ),
        SearchField(
            name="keywords",
            type=SearchFieldDataType.Collection(SearchFieldDataType.String),
            searchable=True,
            filterable=True,
        ),
        SimpleField(
            name="viInsightsUrl",
            type=SearchFieldDataType.String,
            retrievable=True,
        ),
        SimpleField(
            name="url",
            type=SearchFieldDataType.String,
            retrievable=True,
        ),
        SearchField(
            name="content_vector",
            type=SearchFieldDataType.Collection(SearchFieldDataType.Single),
            searchable=True,
            vector_search_dimensions=VECTOR_DIMENSIONS,
            vector_search_profile_name="nab-vector-profile",
        ),
    ]

    vector_search = VectorSearch(
        algorithms=[HnswAlgorithmConfiguration(name="nab-hnsw")],
        profiles=[
            VectorSearchProfile(
                name="nab-vector-profile",
                algorithm_configuration_name="nab-hnsw",
            )
        ],
    )

    semantic_config = SemanticConfiguration(
        name="default",
        prioritized_fields=SemanticPrioritizedFields(
            content_fields=[
                SemanticField(field_name="searchText"),
                SemanticField(field_name="description"),
                SemanticField(field_name="transcript"),
            ],
            keywords_fields=[
                SemanticField(field_name="videoName"),
            ],
        ),
    )

    index = SearchIndex(
        name=INDEX_NAME,
        fields=fields,
        vector_search=vector_search,
        semantic_search=SemanticSearch(configurations=[semantic_config]),
    )

    index_client.create_or_update_index(index)
    print(f"Index ready: {INDEX_NAME}")


def normalize_input_paths(
    segments_files: str | Path | Sequence[str | Path],
) -> list[Path]:
    """Normalize one or more input files into a deduplicated path list."""
    if isinstance(segments_files, (str, Path)):
        raw_paths: Sequence[str | Path] = [segments_files]
    else:
        raw_paths = segments_files

    normalized_paths: list[Path] = []
    seen_paths: set[str] = set()

    for raw_path in raw_paths:
        resolved_path = Path(raw_path).expanduser().resolve()
        resolved_key = str(resolved_path)
        if resolved_key in seen_paths:
            continue
        seen_paths.add(resolved_key)
        normalized_paths.append(resolved_path)

    if not normalized_paths:
        raise SystemExit("ERROR: No final output files were provided.")

    missing_paths = [path for path in normalized_paths if not path.is_file()]
    if missing_paths:
        missing_list = ", ".join(str(path) for path in missing_paths)
        raise SystemExit(f"ERROR: Final output file not found: {missing_list}")

    return normalized_paths


def discover_final_output_files(
    input_dir: str | Path = "video_index",
) -> list[Path]:
    """Discover every final output file in the target directory."""
    return sorted(Path(input_dir).expanduser().glob("*_final_output.json"))


def load_segments_file(segments_file: Path) -> list[dict[str, Any]]:
    """Load and validate a final-output file."""
    with segments_file.open("r", encoding="utf-8") as file_handle:
        payload = json.load(file_handle)

    if not isinstance(payload, list):
        raise SystemExit(
            f"ERROR: Expected a JSON array in {segments_file}, got "
            f"{type(payload).__name__}."
        )

    documents: list[dict[str, Any]] = []
    for item in payload:
        if not isinstance(item, dict):
            raise SystemExit(
                f"ERROR: Expected every document in {segments_file} to be "
                "a JSON object."
            )
        documents.append(item)

    return documents


def load_documents(
    segment_files: Sequence[Path],
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    """Load all final-output files and reject duplicate document ids."""
    documents: list[dict[str, Any]] = []
    document_counts_by_file: dict[str, int] = {}
    seen_document_ids: dict[str, Path] = {}

    for segment_file in segment_files:
        file_documents = load_segments_file(segment_file)
        document_counts_by_file[str(segment_file)] = len(file_documents)

        for document in file_documents:
            document_id = str(document.get("id") or "").strip()
            if not document_id:
                raise SystemExit(
                    "ERROR: Document in "
                    f"{segment_file} is missing the 'id' field."
                )

            previous_path = seen_document_ids.get(document_id)
            if previous_path is not None and previous_path != segment_file:
                raise SystemExit(
                    "ERROR: Duplicate document id "
                    f"'{document_id}' found in {previous_path} and "
                    f"{segment_file}."
                )

            seen_document_ids[document_id] = segment_file
            documents.append(document)

    return documents, document_counts_by_file


def chunked(
    items: Sequence[dict[str, Any]],
    size: int,
) -> Iterator[list[dict[str, Any]]]:
    """Yield fixed-size batches for Azure AI Search uploads."""
    for start in range(0, len(items), size):
        yield list(items[start:start + size])


def build(
    segments_files: str | Path | Sequence[str | Path],
    recreate_index: bool = False,
) -> dict[str, Any]:
    """Embed and upload one or more final-output files to Azure AI Search."""
    check_env()
    input_paths = normalize_input_paths(segments_files)
    documents, document_counts_by_file = load_documents(input_paths)

    if not documents:
        raise SystemExit("ERROR: No documents found in the supplied files.")

    token_provider = get_bearer_token_provider(
        DefaultAzureCredential(),
        "https://cognitiveservices.azure.com/.default",
    )
    openai_client = AzureOpenAI(
        azure_endpoint=OPENAI_ENDPOINT,
        azure_ad_token_provider=token_provider,
        api_version="2024-02-01",
    )

    credential = AzureKeyCredential(SEARCH_KEY)
    index_client = SearchIndexClient(
        endpoint=SEARCH_ENDPOINT,
        credential=credential,
    )
    search_client = SearchClient(
        endpoint=SEARCH_ENDPOINT,
        index_name=INDEX_NAME,
        credential=credential,
    )

    create_index(index_client, recreate=recreate_index)

    print(
        f"\nEmbedding and uploading {len(documents)} segments from "
        f"{len(input_paths)} final output file(s) ..."
    )

    prepared_documents: list[dict[str, Any]] = []
    for index, document in enumerate(documents, start=1):
        embed_text = str(
            document.get("searchText") or document.get("transcript") or ""
        )
        vector = get_embedding(openai_client, embed_text)
        prepared_documents.append({**document, "content_vector": vector})
        print(
            f"  [{index}/{len(documents)}] {document['id']} "
            f"({len(embed_text)} chars embedded)"
        )

    succeeded = 0
    failed_results = []
    for batch_number, batch in enumerate(
        chunked(prepared_documents, UPLOAD_BATCH_SIZE),
        start=1,
    ):
        print(
            f"Uploading batch {batch_number} "
            f"({len(batch)} documents) ..."
        )
        result = search_client.upload_documents(documents=batch)
        succeeded += sum(1 for item in result if item.succeeded)
        failed_results.extend(item for item in result if not item.succeeded)

    print(
        f"\nUploaded {succeeded}/{len(prepared_documents)} documents "
        f"to '{INDEX_NAME}'"
    )

    if failed_results:
        for item in failed_results:
            print(f"  FAILED: {item.key} — {item.error_message}")

    return {
        "indexName": INDEX_NAME,
        "fileCount": len(input_paths),
        "documentCount": len(prepared_documents),
        "uploadedCount": succeeded,
        "failedCount": len(failed_results),
        "documentCountsByFile": document_counts_by_file,
        "inputPaths": [str(path) for path in input_paths],
        "recreateIndex": recreate_index,
    }


def main(argv: list[str] | None = None) -> int:
    """CLI entrypoint for bulk Azure AI Search indexing."""
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--input",
        action="append",
        help=(
            "Path to a final output JSON file. Repeat the flag to provide "
            "multiple files. Defaults to all *_final_output.json files in "
            "--input-dir."
        ),
    )
    parser.add_argument(
        "--input-dir",
        default="video_index",
        help=(
            "Directory used to discover final output files when --input "
            "is omitted."
        ),
    )
    parser.add_argument("--recreate-index", action="store_true")
    args = parser.parse_args(argv)

    input_paths = (
        [Path(value) for value in args.input]
        if args.input
        else discover_final_output_files(args.input_dir)
    )

    if not input_paths:
        print("ERROR: No final output files found.")
        print(
            "Run: python main.py, build the final outputs first, or pass "
            "one or more --input paths."
        )
        return 1

    build(input_paths, recreate_index=args.recreate_index)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
