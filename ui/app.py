"""Sprint 5: Streamlit messenger-style chat UI for IcarusAgent."""

import sys
from pathlib import Path

# Ensure repo root is on sys.path so `agent.*` / `config.*` resolve
# when Streamlit Cloud launches this file as ui/app.py.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import re
import uuid

import streamlit as st

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

active = get_active_model()
if active == "fallback":
    st.caption("Model: ⚠️ fallback: Gemini Flash · ● online")
else:
    st.caption("Model: Llama-3-70B (free) · ● online")

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_CITATION_RE = re.compile(r"Ch\.\d+/[A-Z]+/[A-Z][A-Z0-9 \-]+")


def _extract_citations(text: str) -> list[str]:
    return list(dict.fromkeys(_CITATION_RE.findall(text)))


def _call_agent(question: str) -> str:
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
            if event.is_final_response() and event.content and event.content.parts:
                for part in event.content.parts:
                    if part.text:
                        final_text += part.text
        return final_text or "_(no response — check API key and quota)_"
    except Exception as e:
        return f"⚠️ Agent error: {type(e).__name__}: {str(e)[:200]}"


# ---------------------------------------------------------------------------
# Seed prompts (empty state)
# ---------------------------------------------------------------------------

_SEEDS = [
    "What IEE item maps to an Aspen MIXER block?",
    "Show design bounds for the ANCHOR agitator",
    "List all items in the Agitators category",
]

if not st.session_state.messages:
    st.markdown("**Try one of these:**")
    cols = st.columns(len(_SEEDS))
    for col, seed in zip(cols, _SEEDS):
        if col.button(seed, use_container_width=True):
            st.session_state.messages.append({"role": "user", "content": seed})
            st.rerun()

# ---------------------------------------------------------------------------
# Chat history
# ---------------------------------------------------------------------------

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])
        if msg["role"] == "assistant":
            for cite in _extract_citations(msg["content"]):
                st.caption(f"↳ source: {cite}")

# ---------------------------------------------------------------------------
# Input + response
# ---------------------------------------------------------------------------

if prompt := st.chat_input("Ask about a block or equipment code…"):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        with st.spinner("Consulting IEE…"):
            reply = _call_agent(prompt)
        st.markdown(reply)
        for cite in _extract_citations(reply):
            st.caption(f"↳ source: {cite}")

    st.session_state.messages.append({"role": "assistant", "content": reply})
    st.rerun()
