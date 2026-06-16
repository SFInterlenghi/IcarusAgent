# IcarusAgent

An informational AI assistant for chemical/process engineers that maps Aspen Plus/HYSYS simulation blocks to exact equipment models, design bounds, item symbols, and configuration rules in the Icarus Evaluation Engine (IEE) database.

## Current Capabilities

- [x] Project scaffold and config spine (Sprint 0)
- [x] PDF → SQLite ETL for Chapter 2 Agitators (Sprint 1) — 5 categories, 40 items
- [x] Read-only KB query tools (Sprint 2) — lookup_category, list_items, get_item_detail, search_items
- [x] Resilient model layer with free-model fallback (Sprint 3) — primary→fallback routing, ADK LiteLlm model object
- [x] ADK agent assembly (Sprint 4) — LlmAgent + 4 KB tools + grounding instructions
- [x] Streamlit messenger UI (Sprint 5) — messenger-style chat with seed prompts, citations, model badge
- [x] Full Ch.3–16 equipment catalog (Sprint 6) — 57 categories, 366 items across all chapters

## Architecture

```
User (Streamlit UI)
    │
    ▼
ADK LlmAgent (root_agent.py)
    │
    ├── model_layer.py ──► OpenRouter Llama-3-70B free (primary)
    │                  └─► Google Gemini Flash (fallback on 429/5xx)
    │
    └── tools.py ──────► SQLite KB (icarus_kb.sqlite)
                              │
                    ETL pipeline (etl/)
                              │
                    AspenIcarusV15_Ref.pdf
```

## Setup

### Prerequisites

- Python 3.11+
- `AspenIcarusV15_Ref.pdf` in the project root

### Install

```bash
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### Configure

```bash
cp .env.example .env
# Edit .env with your keys:
#   OPENROUTER_API_KEY — from openrouter.ai (free account)
#   GOOGLE_API_KEY     — from Google AI Studio (unbilled Pro key)
```

## Environment Variables

| Variable | Description | Default |
|---|---|---|
| `OPENROUTER_API_KEY` | OpenRouter API key (free tier) | *(required)* |
| `GOOGLE_API_KEY` | Google AI Studio key (unbilled) | *(required)* |
| `PRIMARY_MODEL` | Primary LLM slug | `openrouter/meta-llama/llama-3-70b-instruct:free` |
| `FALLBACK_MODEL` | Fallback LLM slug | `gemini/gemini-flash-latest` |
| `DB_PATH` | SQLite database path | `data/icarus_kb.sqlite` |
| `PDF_PATH` | Icarus reference PDF path | `AspenIcarusV15_Ref.pdf` |

## Running

```bash
streamlit run ui/app.py
```

## Building the Knowledge Base

```bash
# Full catalog (Ch.2–16)
python -m etl.load_sqlite --chapter 2-16

# Chapter 2 only
python -m etl.load_sqlite --chapter 2
```

## Running Tests

```bash
pytest tests/ -v
```

## Sprint Status

| Sprint | Objective | Status |
|---|---|---|
| 0 | Scaffolding & config | ✅ Complete |
| 1 | ETL: PDF → SQLite (Ch.2) | ✅ Complete |
| 2 | KB query tools | ✅ Complete |
| 3 | Resilient model layer | ✅ Complete (live --probe pending your API keys) |
| 4 | ADK agent assembly | ✅ Complete (live integration tests require API quota) |
| 5 | Streamlit messenger UI | ✅ Complete |
| 6 | Full Ch.3–16 catalog | ✅ Complete — 57 categories, 366 items |

## References

- [Implementation Blueprint](ROADMAP.md)
- [KB Schema](docs/data_schema.md)
- [Model Routing Policy](docs/model_routing.md)
- Aspen Icarus V15 Reference Guide (PDF, 1,492 pages)
