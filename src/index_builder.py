"""
index_builder.py

Creates the nab-video-segments AI Search index and pushes final output
documents with embeddings.

Run after `python main.py` or `python src/build_all_final_outputs.py` has
produced `<video_name>_final_output.json`.

Usage:
    python src/index_builder.py
    python src/index_builder.py \
        --input video_index/flight_simulator_final_output.json
    python src/index_builder.py --recreate-index
"""

import json
import os
import sys
import argparse
from pathlib import Path

from dotenv import load_dotenv
from openai import AzureOpenAI
from azure.identity import DefaultAzureCredential, get_bearer_token_provider
from azure.search.documents import SearchClient
from azure.search.documents.indexes import SearchIndexClient
from azure.search.documents.indexes.models import (
    SearchIndex,
    SearchField,
    SearchFieldDataType,
    SimpleField,
    SearchableField,
    VectorSearch,
    HnswAlgorithmConfiguration,
    VectorSearchProfile,
    SemanticConfiguration,
    SemanticSearch,
    SemanticPrioritizedFields,
    SemanticField,
)
from azure.core.credentials import AzureKeyCredential

ROOT_DIR = Path(__file__).resolve().parent.parent
SRC_DIR = Path(__file__).resolve().parent

load_dotenv(ROOT_DIR / ".env")
load_dotenv(SRC_DIR / ".env")

SEARCH_ENDPOINT = os.getenv("AZURE_SEARCH_ENDPOINT")
SEARCH_KEY = os.getenv("AZURE_SEARCH_API_KEY")
INDEX_NAME = os.getenv("AZURE_SEARCH_INDEX_NAME", "nab-video-segments")
OPENAI_ENDPOINT = os.getenv("AZURE_OPENAI_ENDPOINT")
OPENAI_KEY = os.getenv("AZURE_OPENAI_API_KEY")
EMBEDDING_MODEL = os.getenv(
    "AZURE_OPENAI_EMBEDDING_DEPLOYMENT",
    "text-embedding-3-large",
)

# text-embedding-3-large = 3072 dims; text-embedding-3-small = 1536
VECTOR_DIMENSIONS = 3072


def check_env():
    # AZURE_OPENAI_API_KEY is not required because this uses Entra auth.
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
    response = client.embeddings.create(input=text, model=EMBEDDING_MODEL)
    return response.data[0].embedding


def create_index(index_client: SearchIndexClient, recreate: bool = False):
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


def build(segments_file: str, recreate_index: bool = False):
    check_env()

    # Key auth is disabled on this resource, so authenticate via Entra.
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

    with open(segments_file, "r") as f:
        segments = json.load(f)

    print(f"\nEmbedding and uploading {len(segments)} segments ...")

    documents = []
    for i, seg in enumerate(segments):
        # searchText is the rich merged field — best signal for embedding
        embed_text = seg.get("searchText") or seg.get("transcript", "")
        vector = get_embedding(openai_client, embed_text)
        doc = {**seg, "content_vector": vector}
        documents.append(doc)
        print(
            f"  [{i + 1}/{len(segments)}] {seg['id']} "
            f"({len(embed_text)} chars embedded)"
        )

    result = search_client.upload_documents(documents)
    succeeded = sum(1 for r in result if r.succeeded)
    print(
        f"\nUploaded {succeeded}/{len(documents)} documents "
        f"to '{INDEX_NAME}'"
    )

    if succeeded < len(documents):
        for r in result:
            if not r.succeeded:
                print(f"  FAILED: {r.key} — {r.error_message}")


def find_default_input() -> Path | None:
    """Find a single final output file in the default video_index folder."""
    candidates = sorted(Path("video_index").glob("*_final_output.json"))
    if len(candidates) == 1:
        return candidates[0]
    return None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input")
    parser.add_argument("--recreate-index", action="store_true")
    args = parser.parse_args(argv)

    input_path = Path(args.input) if args.input else find_default_input()

    if input_path is None or not input_path.exists():
        print("ERROR: No final output file found.")
        print(
            "Run: python main.py or pass --input "
            "video_index/<video_name>_final_output.json"
        )
        return 1

    build(str(input_path), recreate_index=args.recreate_index)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
