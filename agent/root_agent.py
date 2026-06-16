"""Sprint 4: ADK LlmAgent wired to model layer + KB query tools.

Public surface:
  build_agent()  → LlmAgent instance ready for use with InMemoryRunner
  root_agent     → module-level singleton (imported by ADK CLI / ui/)

CLI:
  python -m agent.root_agent --ask "What IEE item maps to an Aspen agitated mixing tank?"
"""

import logging
import sys

from google.adk.agents import LlmAgent

from agent.model_layer import make_adk_model
from agent.prompts import SYSTEM_INSTRUCTION
from config.settings import settings

logger = logging.getLogger(__name__)

_DB = settings.DB_PATH


# ---------------------------------------------------------------------------
# Tool wrappers — thin shims that bind db_path from settings so the LLM
# never sees it as a parameter.
# ---------------------------------------------------------------------------

def lookup_category(code: str) -> dict:
    """Look up an equipment category by its two-letter code (e.g. 'AG', 'AT', 'MX').

    Returns a dict with keys: code, name, chapter, page.
    Returns an empty dict if the code is not found.
    """
    from agent.tools import lookup_category as _fn
    return _fn(code, _DB)


def list_items(category_code: str) -> list:
    """List all equipment items in a given category (e.g. 'AG' for Agitators).

    Returns a list of dicts with keys: item_symbol, description, page, citation.
    Returns an empty list if the category is not found.
    """
    from agent.tools import list_items as _fn
    return _fn(category_code, _DB)


def get_item_detail(item_symbol: str, category_code: str = "") -> dict:
    """Get full detail for a specific equipment item including design bounds and materials.

    Args:
        item_symbol: The IEE item symbol, e.g. 'DIRECT', 'ANCHOR', 'PORT PROP'.
        category_code: Optional category to disambiguate items that share a symbol
                       across categories (e.g. 'PORT PROP' exists in both AG and MX).

    Returns a dict with keys: item_symbol, category_code, description, page, citation,
    materials (list), default_material, bounds (list of {parameter, raw_text}).
    Returns an empty dict if not found.
    """
    from agent.tools import get_item_detail as _fn
    return _fn(item_symbol, category_code or None, _DB)


def search_items(keyword: str) -> list:
    """Search for equipment items by keyword (matches item_symbol and description).

    Args:
        keyword: Partial name or description fragment, e.g. 'anchor', 'mixer', 'sanitary'.

    Returns a list of dicts with keys: item_symbol, category_code, description, citation.
    Returns an empty list if no matches found.
    """
    from agent.tools import search_items as _fn
    return _fn(keyword, _DB)


# ---------------------------------------------------------------------------
# Agent factory
# ---------------------------------------------------------------------------

def build_agent() -> LlmAgent:
    """Construct and return the IcarusAgent LlmAgent."""
    model = make_adk_model()
    return LlmAgent(
        name="IcarusAgent",
        description="Maps Aspen Plus/HYSYS simulation blocks to IEE equipment models and design bounds.",
        model=model,
        instruction=SYSTEM_INSTRUCTION,
        tools=[lookup_category, list_items, get_item_detail, search_items],
    )


# Module-level singleton for ADK CLI and Streamlit UI
root_agent = build_agent()


# ---------------------------------------------------------------------------
# CLI: --ask
# ---------------------------------------------------------------------------

def _main() -> None:
    import argparse
    ap = argparse.ArgumentParser(description="IcarusAgent quick query CLI")
    ap.add_argument("--ask", metavar="QUESTION", required=True,
                    help="Ask the agent a question")
    args = ap.parse_args()

    from google.adk.runners import InMemoryRunner
    from google.genai import types

    runner = InMemoryRunner(agent=root_agent, app_name="icarus-cli")
    user_id = "cli-user"
    session_id = "cli-session-1"

    message = types.Content(
        role="user",
        parts=[types.Part(text=args.ask)],
    )

    print(f"\nQ: {args.ask}\n")
    final_text = ""
    for event in runner.run(user_id=user_id, session_id=session_id, new_message=message):
        if event.is_final_response() and event.content and event.content.parts:
            for part in event.content.parts:
                if part.text:
                    final_text += part.text

    if final_text:
        print(f"A: {final_text}\n")
    else:
        print("A: (no text response)\n")


if __name__ == "__main__":
    _main()
