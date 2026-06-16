# IcarusAgent — Implementation Blueprint

> **Status:** Living document. Deviations from this plan must be logged in the Deviation Log at the bottom and require explicit user approval before implementation.

## Grounding Facts

- `AspenIcarusV15_Ref.pdf` = 1,492 pages
- Hierarchy: `Chapter → Equipment Category (2-letter code) → Item/Model symbol → {design bounds, materials, item rules}`
- Ch.2 scope: `AG` (Agitators), `AT` (Agitated Tanks), `BL` (Blenders), `K` (Kneaders), `MX` (Mixers)
- **Chapter 37 (release notes/changelogs) is explicitly out of scope**

## Core Stack

| Layer | Technology |
|---|---|
| Orchestrator | Google ADK (`google-adk`) |
| Model abstraction | LiteLLM |
| Primary model | OpenRouter free Llama-3-70B (`openrouter/meta-llama/llama-3-70b-instruct:free`) |
| Fallback model | Google AI Studio Gemini Flash (`gemini/gemini-flash-latest`) — triggered on 429/5xx |
| Knowledge Base | SQLite (stdlib) — zero-cost, no embeddings |
| PDF parsing | PyMuPDF (`fitz`) |
| UI | Streamlit (messenger-style) |

---

## 1. ARCHITECTURAL OVERVIEW

### 1.1 Directory Layout

```
IcarusAgent/
├── README.md                      # living doc
├── ROADMAP.md                     # this blueprint
├── requirements.txt
├── .env.example                   # key names only, never values
├── .gitignore                     # .env, *.db, __pycache__, .venv
├── config/
│   └── settings.py                # central config: model slugs, paths, env loading
├── data/
│   └── icarus_kb.sqlite            # generated; gitignored (rebuildable)
├── etl/
│   ├── __init__.py
│   ├── extract_pdf.py             # PDF → raw page text (PyMuPDF/fitz)
│   ├── parse_equipment.py         # raw text → structured records
│   ├── load_sqlite.py             # records → SQLite schema
│   └── schema.sql                 # DDL: tables + indexes
├── agent/
│   ├── __init__.py
│   ├── root_agent.py              # ADK LlmAgent definition + instructions
│   ├── model_layer.py             # LiteLLM wrapper w/ primary→fallback routing
│   ├── tools.py                   # ADK FunctionTools querying SQLite
│   └── prompts.py                 # system/instruction strings
├── ui/
│   └── app.py                     # Streamlit messenger-style chat
├── tests/
│   ├── test_etl_parse.py
│   ├── test_kb_queries.py
│   ├── test_model_fallback.py
│   └── test_agent_tools.py
└── docs/
    ├── data_schema.md             # KB schema reference
    └── model_routing.md           # fallback behavior + cost notes
```

### 1.2 Module Responsibilities

| Module | Responsibility | Depends on |
|---|---|---|
| `config/settings.py` | Load `.env`, expose model slugs, `DB_PATH`, API keys | python-dotenv |
| `etl/*` | One-time deterministic PDF→SQLite pipeline (no LLM) | pymupdf, sqlite3 (stdlib) |
| `agent/model_layer.py` | `call_model()` + ADK model object; catch 429+5xx → fallback | litellm, google-adk |
| `agent/tools.py` | Read-only SQLite query tools exposed to the agent | sqlite3 |
| `agent/root_agent.py` | ADK `LlmAgent` wiring model + tools + instructions | google-adk |
| `ui/app.py` | Stateless-per-rerun Streamlit chat invoking the agent | streamlit |

### 1.3 `requirements.txt`

```
google-adk>=0.3.0
litellm>=1.40.0
pymupdf>=1.24.0
python-dotenv>=1.0.0
streamlit>=1.35.0
pytest>=8.0.0
```

### 1.4 `.env.example`

```
OPENROUTER_API_KEY=
GOOGLE_API_KEY=
PRIMARY_MODEL=openrouter/meta-llama/llama-3-70b-instruct:free
FALLBACK_MODEL=gemini/gemini-flash-latest
```

---

## 2. CHAT UI WIREFRAME SPECIFICATION

```
┌──────────────────────────────────────────┐
│  🛰️  IcarusAgent — IEE Equipment Mapper   │  ← st.title
│  Model: Llama-3-70B (free) · ● online     │  ← caption: active model + status dot
├──────────────────────────────────────────┤
│                                          ▲ │
│  ┌────────────────────────────┐           │  user bubble = right-aligned
│  │ How do I map an Aspen Mixer│           │  (st.chat_message("user"))
│  │ block to an IEE agitator?  │           │
│  └────────────────────────────┘           │
│                                            │
│ ┌──────────────────────────────────┐      │  assistant bubble = left-aligned
│ │ 🛰️ Aspen MIXER → IEE Agitated     │      │  (st.chat_message("assistant"))
│ │ Tank (AT), item "MIXER".          │      │
│ │ Bounds: vol 0.5–150 m³ …          │      │
│ │ ↳ source: Ch.2 / AT / MIXER       │      │  ← citation line
│ └──────────────────────────────────┘      │
│                                          ▼ │
├──────────────────────────────────────────┤
│  [ Ask about a block or equipment code… ]│  ← st.chat_input
└──────────────────────────────────────────┘
```

**UI Logic Rules:**
1. `st.session_state.messages = [{role, content, citation?}]` — replay full history on each rerun.
2. On submit → append user msg → `st.spinner("Consulting IEE…")` → agent call → append reply.
3. Header caption shows live `active_model`; shows "⚠️ fallback: Gemini Flash" when 429 promoted fallback.
4. Every grounded fact gets `st.caption("↳ source: Ch.X / CODE / ITEM")`.
5. No write-back buttons — strictly informational.
6. Empty state: 3 seed prompt chips.

---

## 3. DEVELOPMENT ROADMAP BY SPRINTS

> **Rule:** Every sprint ends with all validation steps green → commit → push. Never commit on a red gate.

---

### Sprint 0 — Scaffolding & Config Spine ✅

**Objective:** Repo skeleton, dependency install, config loader. No business logic.

**Files:** `requirements.txt`, `.env.example`, `.gitignore`, `config/settings.py`, all `__init__.py`, `docs/` stubs, `ROADMAP.md`.

**Validation:**
```bash
python -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
python -c "import fitz, litellm, streamlit; print('deps-ok')"
python -c "from config.settings import settings; print(settings.DB_PATH, settings.PRIMARY_MODEL)"
git check-ignore .env   # must return .env
```

---

### Sprint 1 — ETL: PDF → Structured KB (Chapter 2 only)

**Objective:** Deterministic parser for Ch.2 (pp.43–80) into SQLite. Categories `AG, AT, BL, K, MX`. **No LLM.**

**Files:** `etl/extract_pdf.py`, `etl/parse_equipment.py`, `etl/load_sqlite.py`, `etl/schema.sql`, `docs/data_schema.md`, `tests/test_etl_parse.py`.

**Schema:**
```sql
CREATE TABLE equipment_category (code TEXT PRIMARY KEY, name TEXT, chapter INT, page INT);
CREATE TABLE equipment_item (
  id INTEGER PRIMARY KEY, category_code TEXT, item_symbol TEXT,
  description TEXT, page INT,
  FOREIGN KEY(category_code) REFERENCES equipment_category(code));
CREATE TABLE design_bound (
  item_id INT, parameter TEXT, min_val REAL, max_val REAL, unit TEXT,
  FOREIGN KEY(item_id) REFERENCES equipment_item(id));
CREATE TABLE item_material (item_id INT, material TEXT);
CREATE INDEX idx_item_symbol ON equipment_item(item_symbol);
CREATE INDEX idx_cat_code ON equipment_category(code);
```

> ⚠️ **Escalation gate:** If PDF table layouts resist deterministic extraction (merged cells, footnote asterisks), **STOP and ask the user** whether to store bounds as raw text blobs or invest in table reconstruction.

**Validation:**
```bash
python -m etl.extract_pdf --pages 43-80 --check
python -m etl.load_sqlite --chapter 2
pytest tests/test_etl_parse.py -v
```

**Assertions:**
- `equipment_category` contains exactly `{AG, AT, BL, K, MX}`
- `AG` has ≥ 12 items including `DIRECT`, `ANCHOR`, `HIGH SHEAR`
- `AT` includes `MIXER`, `OPEN TOP`, `REACTOR`
- Every `equipment_item.page` within 43–80
- No NULL `item_symbol`; FK integrity via `PRAGMA foreign_key_check`

---

### Sprint 2 — KB Query Tools (read-only)

**Objective:** Pure-Python query functions over SQLite. Deterministic, testable without any model.

**Files:** `agent/tools.py`, `tests/test_kb_queries.py`.

**Tool surface:**
- `lookup_category(code: str) -> dict`
- `list_items(category_code: str) -> list[dict]`
- `get_item_detail(item_symbol: str, category_code: str | None) -> dict`
- `search_items(keyword: str) -> list[dict]` (LIKE over symbol+description)

**Validation:**
```bash
pytest tests/test_kb_queries.py -v
```

**Assertions:**
- `get_item_detail("MIXER", "AT")` returns citation `Ch.2/AT/MIXER` and ≥1 material
- `search_items("anchor")` returns `AG/ANCHOR`
- Unknown code returns empty/None gracefully (no exception)

---

### Sprint 3 — Resilient Model Layer (Primary → Fallback)

**Objective:** `model_layer.py` wrapping LiteLLM. Primary = OpenRouter Llama-3-70B free. On 429/5xx/timeout → Gemini Flash. Surfaces `active_model` for UI badge.

**Files:** `agent/model_layer.py`, `docs/model_routing.md`, `tests/test_model_fallback.py`.

**Logic:** Catch `litellm.RateLimitError`, `litellm.ServiceUnavailableError`, `litellm.APIConnectionError` → switch to `FALLBACK_MODEL`; log which model served the turn.

**Validation:**
```bash
pytest tests/test_model_fallback.py -v   # mocked 429 → assert fallback invoked
python -m agent.model_layer --probe       # live: confirm both slugs resolve
```

> ⚠️ **Gate:** If `--probe` shows either slug 404/unauthorized, **STOP — ask the user** for the correct slug. Do not substitute a billable model.

---

### Sprint 4 — ADK Agent Assembly

**Objective:** ADK `LlmAgent` bound to model layer + Sprint-2 tools + grounding instructions.

**Agent instructions (hard rules):**
- Answer ONLY from tool results
- Always cite `Ch/CODE/ITEM`
- If not in KB, say so — never hallucinate bounds

**Files:** `agent/root_agent.py`, `agent/prompts.py`, `tests/test_agent_tools.py`.

**Validation:**
```bash
pytest tests/test_agent_tools.py -v
python -m agent.root_agent --ask "What IEE item maps to an Aspen agitated mixing tank?"
```

**Assertions:**
- Agent invokes `search_items`/`get_item_detail` (tool-call occurred)
- Reply contains citation token `Ch.2/`
- Out-of-scope query returns honest "not in current KB scope" (no hallucinated data)

---

### Sprint 5 — Streamlit Messenger UI

**Objective:** `ui/app.py` implementing the §2 wireframe.

**Files:** `ui/app.py`, README run section.

**Validation:**
```bash
python -c "import ast; ast.parse(open('ui/app.py').read()); print('syntax-ok')"
streamlit run ui/app.py --server.headless true &
sleep 5 && curl -sSf http://localhost:8501 >/dev/null && echo UI-UP
```

**Manual smoke test (documented in README):** send "anchor agitator bounds" → left bubble with `↳ source: Ch.2/AG/ANCHOR`.

---

### Sprint 6 — Fan-out to Chapters 3–16

**Objective:** Generalize parser to Ch.3–16 (Compressors, Drivers, Heat Transfer … Flares). Chapter 37 explicitly excluded.

**Files:** Update `etl/parse_equipment.py`, regenerate DB, extend tests.

**Validation:**
```bash
python -m etl.load_sqlite --chapter 3-16
pytest tests/ -v
python -m etl.load_sqlite --verify-no-chapter 37
```

**Assertions:**
- Categories include `AC, GC, FN, MOT, TUR, HE…`
- Zero rows from Chapter 37 page range
- All Ch.2 tests still pass

---

## 4. AUXILIARY & MAINTENANCE POLICIES

1. **README is living.** Update at end of each sprint with: current capabilities, exact run commands, env-var table, sprint-status checklist. Never describe unbuilt features as done.
2. **Docs travel with code.** Schema change → update `docs/data_schema.md` in same commit. Model-routing change → update `docs/model_routing.md`.
3. **Commit discipline.** Format: `feat(sprintN): <objective>`. Body lists validation commands that passed. Commit only after all gates green.
4. **Secrets hygiene.** Never commit `.env`, real keys, or `*.sqlite`.
5. **Traceability.** Keep `ROADMAP.md` in repo. Deviations → append to Deviation Log below with user approval.
6. **Escalation gate (hard rule).** On any ambiguity: **STOP, ask the user via `AskUserQuestion`** before writing code.

---

## Open Verification Gates (Sprint 3 resolves these)

1. **Model slugs** — `gemini/gemini-flash-latest` is a placeholder; confirm exact AI Studio slug live.
2. **Bounds parseability** — PDF table footnotes (e.g., `**`) may block deterministic extraction; escalate text-blob vs. table-reconstruction choice.

---

## Deviation Log

*(Empty — no deviations yet)*
