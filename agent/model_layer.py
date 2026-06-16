"""Resilient model layer: OpenRouter Llama-3-70B free (primary) with
Google Gemini Flash fallback on rate-limit / availability errors.

Public surface:
  call_model(messages)  → str response text
  get_active_model()    → "primary" | "fallback" (last call that succeeded)
  make_adk_model()      → google.adk.models.lite_llm.LiteLlm instance for the agent

Both models use LiteLLM so the routing logic and the ADK model object
share the same slug/key configuration from config.settings.
"""

import logging
import os
import sys

import litellm

logger = logging.getLogger(__name__)

# Suppress LiteLLM's verbose per-call logging; keep warnings+
logging.getLogger("LiteLLM").setLevel(logging.WARNING)

# Module-level sentinel: which model served the LAST successful call.
# "primary" until a fallback is used.
_active_model: str = "primary"

# Errors that trigger promotion to the fallback model
_FALLBACK_ERRORS = (
    litellm.RateLimitError,
    litellm.ServiceUnavailableError,
    litellm.APIConnectionError,
)


def _settings():
    from config.settings import settings
    return settings


def _set_api_keys() -> None:
    """Push API keys from settings into the env vars LiteLLM reads."""
    s = _settings()
    if s.OPENROUTER_API_KEY:
        os.environ.setdefault("OPENROUTER_API_KEY", s.OPENROUTER_API_KEY)
    if s.GOOGLE_API_KEY:
        os.environ.setdefault("GOOGLE_API_KEY", s.GOOGLE_API_KEY)


def get_active_model() -> str:
    """Return which model served the last successful call: 'primary' or 'fallback'."""
    return _active_model


def reset_active_model() -> None:
    """Reset the active-model sentinel (used in tests)."""
    global _active_model
    _active_model = "primary"


def call_model(
    messages: list[dict],
    max_tokens: int = 1024,
    temperature: float = 0.2,
) -> str:
    """Call the primary model; promote to fallback on rate-limit / availability errors.

    Args:
        messages:    OpenAI-format message list, e.g. [{"role":"user","content":"..."}]
        max_tokens:  Max tokens in the completion.
        temperature: Sampling temperature (low = more deterministic/factual).

    Returns:
        Response text string.

    Raises:
        The fallback model's exception if both models fail.
    """
    global _active_model
    _set_api_keys()

    s = _settings()
    primary = s.PRIMARY_MODEL
    fallback = s.FALLBACK_MODEL

    try:
        response = litellm.completion(
            model=primary,
            messages=messages,
            max_tokens=max_tokens,
            temperature=temperature,
        )
        _active_model = "primary"
        return response.choices[0].message.content

    except _FALLBACK_ERRORS as primary_err:
        logger.warning(
            "Primary model %s failed (%s: %s); promoting to fallback %s",
            primary, type(primary_err).__name__, primary_err, fallback,
        )
        response = litellm.completion(
            model=fallback,
            messages=messages,
            max_tokens=max_tokens,
            temperature=temperature,
        )
        _active_model = "fallback"
        return response.choices[0].message.content


def make_adk_model(prefer_fallback: bool = False):
    """Return an ADK LiteLlm model object.

    Sprint 4 (root_agent.py) uses this to wire the agent's underlying model.
    By default uses the primary model slug; set prefer_fallback=True to use
    the fallback (e.g. when probing confirms the primary is unavailable).
    """
    from google.adk.models.lite_llm import LiteLlm
    _set_api_keys()
    s = _settings()
    slug = s.FALLBACK_MODEL if prefer_fallback else s.PRIMARY_MODEL
    return LiteLlm(model=slug)


# ---------------------------------------------------------------------------
# CLI: --probe
# ---------------------------------------------------------------------------

def _probe_model(slug: str, label: str) -> bool:
    """Return True if the model responds to a minimal ping call."""
    _set_api_keys()
    try:
        resp = litellm.completion(
            model=slug,
            messages=[{"role": "user", "content": "Reply with the single word: OK"}],
            max_tokens=50,
            temperature=0,
        )
        text = resp.choices[0].message.content.strip()
        print(f"  [{label}] {slug!r}  →  response: {text!r}  ✓")
        return True
    except Exception as e:
        print(f"  [{label}] {slug!r}  →  ERROR: {type(e).__name__}: {e}")
        return False


def _main() -> None:
    import argparse
    ap = argparse.ArgumentParser(description="IcarusAgent model layer CLI")
    ap.add_argument("--probe", action="store_true", help="Verify both model slugs resolve")
    args = ap.parse_args()

    if args.probe:
        s = _settings()
        print("Probing model slugs …")
        primary_ok = _probe_model(s.PRIMARY_MODEL, "primary ")
        fallback_ok = _probe_model(s.FALLBACK_MODEL, "fallback")

        if primary_ok and fallback_ok:
            print("\nprobe-ok: both models reachable")
            sys.exit(0)
        else:
            print(
                "\n⚠️  ESCALATION GATE: one or more model slugs failed."
                "\nDo NOT substitute a paid model."
                "\nVerify your API keys in .env and the exact slug names, then re-run --probe."
            )
            sys.exit(1)


if __name__ == "__main__":
    _main()
