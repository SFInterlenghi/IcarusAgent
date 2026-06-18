"""Sprint 5: Streamlit messenger-style chat UI for IcarusAgent."""

import sys
from pathlib import Path

# Ensure repo root is on sys.path so `agent.*` / `config.*` resolve
# when Streamlit Cloud launches this file as ui/app.py.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import os
import re
import uuid

import streamlit as st

# Bridge Streamlit Cloud secrets into env vars so config/settings.py
# (which uses os.getenv) can see API keys set in the secrets panel.
for key in ("OPENROUTER_API_KEY", "GOOGLE_API_KEY", "PRIMARY_MODEL", "FALLBACK_MODEL"):
    if key not in os.environ and key in st.secrets:
        os.environ[key] = st.secrets[key]

from agent.model_layer import get_active_model
from agent.root_agent import build_agent

# ---------------------------------------------------------------------------
# Page config
# ---------------------------------------------------------------------------

st.set_page_config(
    page_title="IcarusAgent",
    page_icon="🛰️",
    layout="centered",
)

# ---------------------------------------------------------------------------
# Session state bootstrap
# ---------------------------------------------------------------------------

if "messages" not in st.session_state:
    st.session_state.messages = []

if "runner" not in st.session_state:
    from google.adk.runners import InMemoryRunner
    agent = build_agent()
    runner = InMemoryRunner(agent=agent, app_name="icarus-ui")
    session_id = f"ui-{uuid.uuid4().hex[:8]}"
    runner.session_service.create_session_sync(
        app_name="icarus-ui",
        user_id="ui-user",
        session_id=session_id,
    )
    st.session_state.runner = runner
    st.session_state.session_id = session_id

# ---------------------------------------------------------------------------
# Header
# ---------------------------------------------------------------------------

st.title("🛰️ IcarusAgent — IEE Equipment Mapper")

from config.settings import settings


def _short_model(slug: str) -> str:
    """Last path segment of a model slug, e.g. 'nemotron-3-ultra-550b-a55b:free'."""
    return slug.rsplit("/", 1)[-1] if slug else "unknown"


active = get_active_model()
if active == "fallback":
    st.caption(f"Model: ⚠️ fallback: {_short_model(settings.FALLBACK_MODEL)} · ● online")
else:
    st.caption(f"Model: {_short_model(settings.PRIMARY_MODEL)} · ● online")

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_CITATION_RE = re.compile(r"Ch\.\d+/[A-Z]+/[A-Z][A-Z0-9 \-]+")


def _extract_citations(text: str) -> list[str]:
    return list(dict.fromkeys(_CITATION_RE.findall(text)))


def _humanize_tool(name: str, args: dict) -> str:
    """Turn a raw tool call into a friendly progress line for the status box."""
    if name == "search_items":
        return f"🔍 Searching the IEE reference for “{args.get('keyword', '')}”…"
    if name == "list_items":
        return f"📋 Listing items in category {args.get('category_code', '')}…"
    if name == "get_item_detail":
        return f"📐 Reading design bounds for {args.get('item_symbol', '')}…"
    if name == "lookup_category":
        return f"🗂️ Looking up category {args.get('code', '')}…"
    return f"⚙️ Running {name}…"


def _call_agent(question: str, status=None) -> str:
    from google.genai import types

    try:
        runner = st.session_state.runner
        session_id = st.session_state.session_id
        message = types.Content(role="user", parts=[types.Part(text=question)])
        final_text = ""
        for event in runner.run(
            user_id="ui-user",
            session_id=session_id,
            new_message=message,
        ):
            content = getattr(event, "content", None)
            parts = getattr(content, "parts", None) if content else None
            if parts and status is not None:
                for part in parts:
                    fc = getattr(part, "function_call", None)
                    if fc and getattr(fc, "name", None):
                        line = _humanize_tool(fc.name, dict(getattr(fc, "args", {}) or {}))
                        status.update(label=line)
                        status.write(line)
            if event.is_final_response() and parts:
                for part in parts:
                    if part.text:
                        final_text += part.text
        return final_text or "_(no response — check API key and quota)_"
    except Exception as e:
        return f"⚠️ Agent error: {type(e).__name__}: {str(e)[:200]}"


_CLARIFY_LINE_RE = re.compile(r"^\s*CLARIFY:\s*(.+)$")
_OPTION_LINE_RE = re.compile(r"^\s*[-*]\s+(.+)$")


def _parse_clarify(text: str):
    """Split an assistant reply into (clean_text, [{question, options}, ...]).

    A clarify block is a line `CLARIFY: <q>` followed by one or more `- option` lines.
    """
    lines = text.splitlines()
    clean: list[str] = []
    questions: list[dict] = []
    i = 0
    while i < len(lines):
        m = _CLARIFY_LINE_RE.match(lines[i])
        if m:
            question = m.group(1).strip()
            opts: list[str] = []
            i += 1
            while i < len(lines):
                om = _OPTION_LINE_RE.match(lines[i])
                if not om:
                    break
                opts.append(om.group(1).strip())
                i += 1
            if opts:
                questions.append({"question": question, "options": opts})
            else:
                clean.append(lines[i - 1])  # malformed — keep original line
            continue
        clean.append(lines[i])
        i += 1
    return "\n".join(clean).strip(), questions


# ---------------------------------------------------------------------------
# Seed prompts (empty state)
# ---------------------------------------------------------------------------

_SEEDS = [
    "What IEE item maps to an Aspen MIXER block?",
    "Show design bounds for the ANCHOR agitator",
    "List all items in the Agitators category",
]

_seed_prompt: str | None = None

if not st.session_state.messages:
    st.markdown("**Try one of these:**")
    cols = st.columns(len(_SEEDS))
    for col, seed in zip(cols, _SEEDS):
        if col.button(seed, use_container_width=True):
            _seed_prompt = seed

# ---------------------------------------------------------------------------
# Chat history (with clarify-question buttons on the latest message)
# ---------------------------------------------------------------------------

_clarify_answer: str | None = None
_last_idx = len(st.session_state.messages) - 1

for idx, msg in enumerate(st.session_state.messages):
    with st.chat_message(msg["role"]):
        if msg["role"] == "assistant":
            clean, questions = _parse_clarify(msg["content"])
            st.markdown(clean)
            for cite in _extract_citations(clean):
                st.caption(f"↳ source: {cite}")
            # Only the latest assistant message gets interactive buttons.
            if idx == _last_idx and questions:
                for qi, q in enumerate(questions):
                    st.markdown(f"**{q['question']}**")
                    bcols = st.columns(len(q["options"]))
                    for oi, opt in enumerate(q["options"]):
                        if bcols[oi].button(opt, key=f"clarify-{idx}-{qi}-{oi}"):
                            _clarify_answer = opt
        else:
            st.markdown(msg["content"])

# ---------------------------------------------------------------------------
# Input + response
# ---------------------------------------------------------------------------

prompt = st.chat_input("Ask about a block or equipment code…") or _seed_prompt or _clarify_answer

if prompt:
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        with st.status("Consulting IEE…", expanded=True) as status:
            reply = _call_agent(prompt, status)
            status.update(label="Done", state="complete", expanded=False)
        clean, _ = _parse_clarify(reply)
        st.markdown(clean)
        for cite in _extract_citations(clean):
            st.caption(f"↳ source: {cite}")

    st.session_state.messages.append({"role": "assistant", "content": reply})
    st.rerun()
