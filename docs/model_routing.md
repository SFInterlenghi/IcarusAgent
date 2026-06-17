# IcarusAgent — Model Routing & Cost Policy

> Updated each time `agent/model_layer.py` changes.

## Zero-Cost Mandate

This system must never incur LLM API costs. All models must be free-tier or unbilled.

## Model Configuration

| Role | Model | Provider | Cost |
|---|---|---|---|
| Primary | `openrouter/nex-agi/nex-n2-pro:free` | OpenRouter | $0 (free tier) |
| Fallback | `gemini/gemini-flash-latest` | Google AI Studio | $0 (unbilled Pro key) |

> Nex-N2-Pro is an agentic MoE model with native **function-calling** support — required
> because the agent answers exclusively through tool calls. Any substitute primary/fallback
> model MUST support tool/function calling or the agent will break.

> ⚠️ Exact slugs verified in Sprint 3 `--probe`. If either slug fails, escalate to user — do not substitute a paid model.

## Routing Logic

```
User query
    │
    ▼
call_model(prompt)
    │
    ├─── PRIMARY_MODEL (OpenRouter Llama-3-70B free)
    │         │
    │    success ──────────────────────────────► return response
    │         │
    │    429 / 5xx / ConnectionError
    │         │
    │         ▼
    └─── FALLBACK_MODEL (Gemini Flash)
              │
         success ──────────────────────────────► return response + set active_model="fallback"
              │
         failure ─────────────────────────────► raise + surface error to user
```

## Error Classes Triggering Fallback

- `litellm.RateLimitError` (HTTP 429)
- `litellm.ServiceUnavailableError` (HTTP 503/502)
- `litellm.APIConnectionError` (network timeout)

## `active_model` Surface

`model_layer.py` exposes `get_active_model() -> str` for the Streamlit UI badge. Returns:
- `"primary"` — Llama-3-70B serving
- `"fallback"` — Gemini Flash serving (shown with ⚠️ in UI)

`reset_active_model()` resets to `"primary"` — used in tests only.

## ADK Model Object

`make_adk_model(prefer_fallback=False)` returns a `google.adk.models.lite_llm.LiteLlm`
instance for wiring into the ADK agent (Sprint 4).

**Note (ADK v2.2.0):** ADK warns that Gemini models should use its native `Gemini()`
class rather than `LiteLlm(model="gemini/...")` for better reliability. This will be
evaluated in Sprint 4 — for the fallback path in `call_model()` (which uses
`litellm.completion` directly, not the ADK model object) there is no change needed.

## Verification Gate (Sprint 3)

Run `python -m agent.model_layer --probe` with API keys set in `.env` to confirm
both slugs resolve live. If either returns 404/401, stop and update the slug — do
not substitute a paid model.

## Status

| Sprint | Gate | Status |
|---|---|---|
| Sprint 3 | Mocked fallback tests (12/12) | ✅ Complete |
| Sprint 3 | Live `--probe` (requires keys in .env) | Pending user run |
