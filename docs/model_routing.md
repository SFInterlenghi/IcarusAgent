# IcarusAgent — Model Routing & Cost Policy

> Updated each time `agent/model_layer.py` changes.

## Zero-Cost Mandate

This system must never incur LLM API costs. All models must be free-tier or unbilled.

## Model Configuration

| Role | Model | Provider | Cost |
|---|---|---|---|
| Primary | `openrouter/meta-llama/llama-3-70b-instruct:free` | OpenRouter | $0 (free tier) |
| Fallback | `gemini/gemini-flash-latest` | Google AI Studio | $0 (unbilled Pro key) |

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
