# IcarusAgent — Testing Guide

This document walks you through everything needed to go from a fresh clone to a working
chat session. All code is complete; you only need an API key and the reference PDF.

---

## Prerequisites

| Item | Where to get it |
|---|---|
| Python 3.11+ | python.org |
| `AspenIcarusV15_Ref.pdf` | Your Aspen Icarus V15 installation or license portal |
| At least one API key | See options below |

### API Key Options

**Option A — Gemini only (simplest, no cost)**
Get a free key from [aistudio.google.com](https://aistudio.google.com) → **Get API key**.
You will run both primary and fallback on Gemini Flash (free tier: 15 req/min, 1500 req/day).

**Option B — Full setup (OpenRouter primary + Gemini fallback)**
- OpenRouter key: [openrouter.ai](https://openrouter.ai) → Keys → Create Key (free tier)
- Google key: same as Option A

---

## Setup

```bash
# 1. Clone and enter the repo
git clone https://github.com/sfinterlenghi/icarusagent.git
cd icarusagent
git checkout claude/hopeful-albattani-a3loxm   # current development branch

# 2. Create virtual environment
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Place the PDF in the project root
#    The file must be named exactly: AspenIcarusV15_Ref.pdf

# 5. Configure API keys
cp .env.example .env
```

Edit `.env` — choose the appropriate block:

**Option A (Gemini only):**
```
OPENROUTER_API_KEY=
GOOGLE_API_KEY=your-google-key-here
PRIMARY_MODEL=gemini/gemini-flash-latest
FALLBACK_MODEL=gemini/gemini-flash-latest
DB_PATH=data/icarus_kb.sqlite
PDF_PATH=AspenIcarusV15_Ref.pdf
```

**Option B (OpenRouter primary + Gemini fallback):**
```
OPENROUTER_API_KEY=your-openrouter-key-here
GOOGLE_API_KEY=your-google-key-here
PRIMARY_MODEL=openrouter/meta-llama/llama-3-70b-instruct:free
FALLBACK_MODEL=gemini/gemini-flash-latest
DB_PATH=data/icarus_kb.sqlite
PDF_PATH=AspenIcarusV15_Ref.pdf
```

---

## Build the Knowledge Base

This is a one-time step that parses the PDF and populates the SQLite database.
The database is not committed to the repo — you must build it locally.

```bash
python -m etl.load_sqlite --chapter 2-16
```

Expected output:
```
Processing chapter 2…
  Found 5 categories, 40 items
Processing chapter 3…
  Found 3 categories, 18 items
...
Processing chapter 16…
  Found 2 categories, 7 items
DB written: data/icarus_kb.sqlite
```

Total: **57 categories, 366 items** across Chapters 2–16.

---

## Verify the Setup

### 1. Check model connectivity
```bash
python -m agent.model_layer --probe
```
Expected:
```
Probing model slugs …
  [primary ] 'gemini/gemini-flash-latest'  →  response: 'OK'  ✓
  [fallback] 'gemini/gemini-flash-latest'  →  response: 'OK'  ✓

probe-ok: both models reachable
```

### 2. Run the automated test suite
```bash
pytest tests/ -v
```
Expected: **64 passed** (the 2 live integration tests in `test_agent_tools.py` are
automatically skipped when no `GOOGLE_API_KEY` is set, and may be skipped if the
daily free-tier quota is exhausted — this is normal).

### 3. Quick CLI smoke test
```bash
python -m agent.root_agent --ask "What IEE item maps to an Aspen MIXER block?"
```
Expected response includes a citation like `Ch.2/AT/MIXER`.

---

## Run the Chat UI

```bash
streamlit run ui/app.py
```

Open [http://localhost:8501](http://localhost:8501) in your browser.

---

## Manual Test Cases

These are the acceptance tests for each sprint feature. Run them in the chat UI
or via the `--ask` CLI.

### KB Query Tests (no LLM needed — test the tools directly)
```bash
# Verify Ch.2 agitator detail
python -c "
from agent.tools import get_item_detail
from config.settings import settings
r = get_item_detail('ANCHOR', 'AG', settings.DB_PATH)
print(r['citation'])      # Expected: Ch.2/AG/ANCHOR
print(r['materials'])     # Expected: list with CS, SS304 etc.
print(r['bounds'][:2])    # Expected: list of (parameter, raw_text) tuples
"

# Verify Ch.5 heat exchanger is in KB
python -c "
from agent.tools import lookup_category
from config.settings import settings
print(lookup_category('HE', settings.DB_PATH))   # Expected: {code: HE, name: Heat Exchangers, chapter: 5}
"

# Verify search across chapters
python -c "
from agent.tools import search_items
from config.settings import settings
results = search_items('compressor', settings.DB_PATH)
print([r['citation'] for r in results[:5]])
"
```

### Chat UI Tests (requires API key + running UI)

| Query | Expected behaviour |
|---|---|
| `"What IEE item maps to an Aspen MIXER block?"` | Response cites `Ch.2/AT/MIXER`, mentions volume bounds |
| `"Show design bounds for the ANCHOR agitator"` | Cites `Ch.2/AG/ANCHOR`, lists parameters like Driver Power |
| `"List all items in the Agitators category"` | Returns all 12 AG items with citations |
| `"What compressor models are available in Icarus?"` | Lists items from AC and GC categories (Ch.3) |
| `"What materials are available for centrifugal pumps?"` | Cites items from CP (Ch.7) |
| `"What are the design bounds for a nuclear reactor?"` | Agent says item is outside KB scope — no hallucination |
| `"Tell me about TEMA shell-and-tube exchangers"` | Agent searches, finds HE items or states not in KB |

### Grounding / Anti-Hallucination Test

This is the most important test for an informational tool:

1. Ask: `"What is the maximum pressure rating for a DIRECT agitator?"`
2. The agent must either:
   - Return the exact value from the PDF (`Ch.2/AG/DIRECT` bounds), or
   - Say the parameter is not in its data
3. **FAIL condition:** If the agent invents a number not in the KB, grounding has failed.

---

## Known Limitations

| Limitation | Detail |
|---|---|
| Free-tier rate limit | Gemini Flash: 15 req/min, 1500 req/day. Heavy testing exhausts the daily quota. |
| PDF required locally | `AspenIcarusV15_Ref.pdf` is not redistributable — must come from your Aspen license. |
| Ch.37 excluded | Release notes (Ch.37) are deliberately not parsed — the agent will say so if asked. |
| Model badge vs. fallback | The header badge tracks `call_model()` state. The ADK agent uses its own model object and does not route through `call_model()`. The badge is informational only. |
| Multi-code categories | Ch.6 "Packing, Linings (PAK, LIN)" is stored under PAK only. |

---

## What Each Sprint Added

| Sprint | Feature | Test file |
|---|---|---|
| 0 | Scaffolding, config | — |
| 1 | ETL: PDF → SQLite (Ch.2) | `tests/test_etl_parse.py` |
| 2 | KB query tools | `tests/test_kb_queries.py` |
| 3 | Model layer + fallback routing | `tests/test_model_fallback.py` |
| 4 | ADK agent assembly | `tests/test_agent_tools.py` |
| 5 | Streamlit chat UI | manual (UI) |
| 6 | Full Ch.3–16 catalog | `tests/test_sprint6_etl.py` |
