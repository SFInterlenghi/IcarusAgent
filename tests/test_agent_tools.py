"""Sprint 4 validation: ADK agent assembly.

Structure tests run without API keys (always).
Integration tests require GOOGLE_API_KEY and are skipped when absent.
"""

import pytest
from unittest.mock import patch, MagicMock
from config.settings import settings


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _has_api_key() -> bool:
    return bool(settings.GOOGLE_API_KEY)


_integration = pytest.mark.skipif(
    not _has_api_key(),
    reason="GOOGLE_API_KEY not set — skipping live agent tests",
)


def _collect_events(runner, user_id: str, session_id: str, question: str) -> tuple[list, str]:
    """Send one message in an existing session and return (events, final_text)."""
    from google.genai import types
    message = types.Content(role="user", parts=[types.Part(text=question)])
    events = list(runner.run(user_id=user_id, session_id=session_id, new_message=message))
    final_text = ""
    for ev in events:
        if ev.is_final_response() and ev.content and ev.content.parts:
            for part in ev.content.parts:
                if part.text:
                    final_text += part.text
    return events, final_text


@pytest.fixture(scope="module")
def live_runner():
    """Shared InMemoryRunner + session for all integration tests (one per module run)."""
    from google.adk.runners import InMemoryRunner
    from agent.root_agent import build_agent

    agent = build_agent()
    runner = InMemoryRunner(agent=agent, app_name="itest")
    runner.session_service.create_session_sync(
        app_name="itest", user_id="itest-user", session_id="itest-session"
    )
    return runner


# ---------------------------------------------------------------------------
# Structure tests (no API key needed)
# ---------------------------------------------------------------------------

def test_build_agent_returns_llm_agent():
    from google.adk.agents import LlmAgent
    from agent.root_agent import build_agent
    agent = build_agent()
    assert isinstance(agent, LlmAgent)


def test_agent_name():
    from agent.root_agent import root_agent
    assert root_agent.name == "IcarusAgent"


def test_agent_has_four_tools():
    from agent.root_agent import root_agent
    assert len(root_agent.tools) == 4


def test_agent_tool_names():
    from agent.root_agent import root_agent
    names = {t.name if hasattr(t, "name") else t.__name__ for t in root_agent.tools}
    assert "lookup_category" in names
    assert "list_items" in names
    assert "get_item_detail" in names
    assert "search_items" in names


def test_agent_instruction_contains_grounding_rules():
    from agent.root_agent import root_agent
    instruction = root_agent.instruction
    assert "GROUNDING RULES" in instruction
    assert "Ch." in instruction  # citation format present
    assert "NEVER invent" in instruction
    assert "engineering suggestion" in instruction  # consultative behavior


def test_root_agent_singleton_is_llm_agent():
    from google.adk.agents import LlmAgent
    from agent.root_agent import root_agent
    assert isinstance(root_agent, LlmAgent)


def test_tool_wrappers_lookup_category():
    from agent.root_agent import lookup_category
    result = lookup_category("AG")
    assert result["code"] == "AG"
    assert result["chapter"] == 2


def test_tool_wrappers_list_items():
    from agent.root_agent import list_items
    items = list_items("AG")
    assert len(items) == 12


def test_tool_wrappers_get_item_detail():
    from agent.root_agent import get_item_detail
    r = get_item_detail("DIRECT", "AG")
    assert r["citation"] == "Ch.2/AG/DIRECT"
    assert r["bounds"]


def test_tool_wrappers_search_items():
    from agent.root_agent import search_items
    results = search_items("anchor")
    symbols = [r["item_symbol"] for r in results]
    assert "ANCHOR" in symbols


def test_tool_wrapper_get_item_empty_category():
    """get_item_detail with empty category_code falls back to first match."""
    from agent.root_agent import get_item_detail
    r = get_item_detail("STATIONARY", "")
    assert r["item_symbol"] == "STATIONARY"


def test_tool_wrapper_search_no_match():
    from agent.root_agent import search_items
    assert search_items("xyznonexistentxyz") == []


# ---------------------------------------------------------------------------
# Integration tests (requires GOOGLE_API_KEY)
# ---------------------------------------------------------------------------

@_integration
def test_agent_happy_path(live_runner):
    """Agent invokes a tool and includes a Ch.2/ citation for an in-KB query.

    Covers: tool-call occurred, citation format, correct item returned.
    """
    events, text = _collect_events(
        live_runner, "itest-user", "itest-session",
        "What are the design bounds and materials for the ANCHOR agitator?",
    )
    tool_calls = [
        part.function_call.name
        for ev in events
        if ev.content and ev.content.parts
        for part in ev.content.parts
        if part.function_call
    ]
    assert tool_calls, f"No tool calls found in events: {events}"
    assert "Ch.2/" in text, f"Citation missing from response: {text!r}"
    assert "ANCHOR" in text, f"Expected ANCHOR in response: {text!r}"


@_integration
def test_agent_out_of_scope_does_not_hallucinate(live_runner):
    """Agent must acknowledge missing data for equipment not in the loaded KB.

    Waits for free-tier rate-limit window to reset before calling.
    """
    import time
    time.sleep(15)  # free tier: 5 req/min; pause ensures we don't exceed quota

    _, text = _collect_events(
        live_runner, "itest-user", "itest-session",
        "What are the design bounds for a centrifugal compressor in Icarus?",
    )
    lower = text.lower()
    honest = (
        "not in" in lower
        or "scope" in lower
        or "not available" in lower
        or "cannot" in lower
        or "chapter 3" in lower
        or "not yet" in lower
    )
    assert honest, (
        f"Agent may have hallucinated — response doesn't acknowledge missing data:\n{text}"
    )
