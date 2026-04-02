## Resource Documentation

### Azure Content Understanding

| Resource | URL | Notes |
|----------|-----|-------|
| Overview (GA `2025-11-01`) | <https://learn.microsoft.com/en-us/azure/ai-services/content-understanding/overview> | Now GA; requires Microsoft Foundry Resource |
| Video solutions & `prebuilt-videoSearch` | <https://learn.microsoft.com/en-us/azure/ai-services/content-understanding/video/overview> | Constraints: ~1 FPS sampling, 512 × 512 px frames |
| REST API Quickstart | <https://learn.microsoft.com/en-us/azure/ai-services/content-understanding/quickstart/use-rest-api> | API version `2025-11-01`; requires GPT-4.1, GPT-4.1-mini, text-embedding-3-large deployments |
| Content Understanding Studio | <https://contentunderstanding.ai.azure.com> | UI for testing analyzers without code |
| Analyzer Templates | <https://github.com/Azure-Samples/azure-ai-content-understanding-python/tree/main/analyzer_templates> | Pre-built templates including `prebuilt-videoSearch` |

### Azure AI Search

| Resource | URL | Notes |
|----------|-----|-------|
| What is Azure AI Search | <https://learn.microsoft.com/en-us/azure/search/search-what-is-azure-search> | Supports full-text, vector, hybrid, multimodal |
| Agentic Retrieval Overview | <https://learn.microsoft.com/en-us/azure/search/agentic-retrieval-overview> | **Public Preview** — region restricted; requires semantic ranker; gpt-4o/4.1/5 only for query planning |
| Integrated Vectorization | <https://learn.microsoft.com/en-us/azure/search/vector-search-integrated-vectorization> | Simplest path to embed chunks automatically at index time |
| Import Vectors Quickstart (portal) | <https://learn.microsoft.com/en-us/azure/search/search-get-started-portal-import-vectors> | Low-code indexing wizard |

### Content Understanding + AI Search (End-to-End Sample)

| Resource | URL | Notes |
|----------|-----|-------|
| **Primary sample repo** | <https://github.com/Azure-Samples/azure-ai-search-with-content-understanding-python> | Has `search_with_video_webapp.ipynb` + Node.js video search web app |
| `search_with_video.ipynb` | Inside repo `/notebooks/` | Extract CU fields → index to AI Search |
| `search_with_video_webapp.ipynb` | Inside repo `/notebooks/` | Full RAG search with video visualization — closest to NAB demo |
| Node.js Video Search App | Inside repo `/nodejs/video-search-app/` | Ready-made front-end; deploy via `azd up` |
| General CU Python Samples | <https://github.com/Azure-Samples/azure-ai-content-understanding-python> | Content extraction notebooks |

### Azure AI Video Indexer

| Resource | URL | Notes |
|----------|-----|-------|
| Overview | <https://learn.microsoft.com/en-us/azure/azure-video-indexer/video-indexer-overview> | Mature service; 30+ AI models; cloud and Arc edge |
| Generative AI with VI | <https://learn.microsoft.com/en-us/azure/azure-video-indexer/generative_ai_with_vi> | Supports GPT-3.5/4 prompts and Q&A; LLM models limited to GPT3.5 Turbo / GPT4 |
| Search for exact moments | <https://learn.microsoft.com/en-us/azure/azure-video-indexer/video-indexer-search> | Portal + embed widget for player-insights sync |
| VI API Quickstart | <https://learn.microsoft.com/en-us/azure/azure-video-indexer/video-indexer-use-apis> | Requires paid standard account (not trial) |
| VI Embed Widgets | <https://learn.microsoft.com/en-us/azure/azure-video-indexer/video-indexer-embed-widgets> | **Player + Insights widgets** — easiest visual demo path with VI |
| VI Samples (GitHub) | <https://github.com/Azure-Samples/azure-video-indexer-samples> | Includes API samples and BYO model samples |
| Face recognition intake form | <https://aka.ms/facerecognition> | **Limited Access** — apply separately if needed |

### Microsoft Foundry (Agent / Web App Deployment)

| Resource | URL | Notes |
|----------|-----|-------|
| Foundry Portal | <https://ai.azure.com> | Classic portal still supports "Deploy to Web App" from Playground |
| Foundry IQ / Agentic Knowledge | <https://learn.microsoft.com/en-us/azure/ai-foundry/agents/concepts/what-is-foundry-iq> | Powered by Azure AI Search agentic retrieval (preview) |
| Deployment Overview | <https://learn.microsoft.com/en-us/azure/foundry-classic/concepts/deployments-overview> | Classic portal; use Foundry resources (not AI Hub) for widest capability |

### Microsoft Copilot Studio

| Resource | URL | Notes |
|----------|-----|-------|
| Generative Answers with Azure OpenAI | <https://learn.microsoft.com/en-us/microsoft-copilot-studio/nlu-generative-answers-azure-openai> | **Preview** — not production-ready |
| Add Knowledge Sources | <https://learn.microsoft.com/en-us/microsoft-copilot-studio/knowledge-copilot-studio> | Azure AI Search supported as knowledge source |
