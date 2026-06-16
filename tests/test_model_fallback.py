"""Sprint 3 validation: model layer fallback logic (fully mocked, no live API calls)."""

from unittest.mock import MagicMock, patch, call
import pytest
import litellm

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _mock_response(text: str = "OK") -> MagicMock:
    """Build a minimal litellm-style completion response mock."""
    msg = MagicMock()
    msg.content = text
    choice = MagicMock()
    choice.message = msg
    resp = MagicMock()
    resp.choices = [choice]
    return resp


def _rate_limit_error():
    return litellm.RateLimitError(
        message="rate limit exceeded",
        model="llama-3-70b",
        llm_provider="openrouter",
    )


def _unavailable_error():
    return litellm.ServiceUnavailableError(
        message="service unavailable",
        model="llama-3-70b",
        llm_provider="openrouter",
    )


def _connection_error():
    return litellm.APIConnectionError(
        message="connection failed",
        model="llama-3-70b",
        llm_provider="openrouter",
    )


MESSAGES = [{"role": "user", "content": "test prompt"}]

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def reset_state():
    """Reset module-level active_model between tests."""
    from agent import model_layer
    model_layer.reset_active_model()
    yield
    model_layer.reset_active_model()


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------

def test_primary_success_returns_text():
    with patch("litellm.completion", return_value=_mock_response("hello")) as mock:
        from agent.model_layer import call_model, get_active_model
        result = call_model(MESSAGES)
    assert result == "hello"
    assert get_active_model() == "primary"
    assert mock.call_count == 1


def test_primary_success_uses_primary_slug():
    from config.settings import settings
    with patch("litellm.completion", return_value=_mock_response()) as mock:
        from agent.model_layer import call_model
        call_model(MESSAGES)
    called_model = mock.call_args[1]["model"]
    assert called_model == settings.PRIMARY_MODEL


# ---------------------------------------------------------------------------
# Fallback on rate limit
# ---------------------------------------------------------------------------

def test_rate_limit_triggers_fallback():
    from agent.model_layer import call_model, get_active_model
    with patch("litellm.completion") as mock:
        mock.side_effect = [_rate_limit_error(), _mock_response("fallback text")]
        result = call_model(MESSAGES)
    assert result == "fallback text"
    assert get_active_model() == "fallback"
    assert mock.call_count == 2


def test_rate_limit_second_call_uses_fallback_slug():
    from config.settings import settings
    with patch("litellm.completion") as mock:
        mock.side_effect = [_rate_limit_error(), _mock_response()]
        from agent.model_layer import call_model
        call_model(MESSAGES)
    fallback_call = mock.call_args_list[1]
    assert fallback_call[1]["model"] == settings.FALLBACK_MODEL


# ---------------------------------------------------------------------------
# Fallback on service unavailable
# ---------------------------------------------------------------------------

def test_service_unavailable_triggers_fallback():
    from agent.model_layer import call_model, get_active_model
    with patch("litellm.completion") as mock:
        mock.side_effect = [_unavailable_error(), _mock_response("ok")]
        result = call_model(MESSAGES)
    assert result == "ok"
    assert get_active_model() == "fallback"


# ---------------------------------------------------------------------------
# Fallback on connection error
# ---------------------------------------------------------------------------

def test_connection_error_triggers_fallback():
    from agent.model_layer import call_model, get_active_model
    with patch("litellm.completion") as mock:
        mock.side_effect = [_connection_error(), _mock_response("ok")]
        result = call_model(MESSAGES)
    assert result == "ok"
    assert get_active_model() == "fallback"


# ---------------------------------------------------------------------------
# Both models fail
# ---------------------------------------------------------------------------

def test_both_fail_raises_exception():
    from agent.model_layer import call_model
    with patch("litellm.completion") as mock:
        mock.side_effect = [_rate_limit_error(), _unavailable_error()]
        with pytest.raises(litellm.ServiceUnavailableError):
            call_model(MESSAGES)


# ---------------------------------------------------------------------------
# Active model tracking
# ---------------------------------------------------------------------------

def test_active_model_resets_to_primary_on_next_success():
    """After a fallback, the next successful primary call resets the badge."""
    from agent.model_layer import call_model, get_active_model

    with patch("litellm.completion") as mock:
        # First call: primary fails → fallback
        mock.side_effect = [_rate_limit_error(), _mock_response("fb")]
        call_model(MESSAGES)
    assert get_active_model() == "fallback"

    with patch("litellm.completion", return_value=_mock_response("primary again")):
        result = call_model(MESSAGES)
    assert result == "primary again"
    assert get_active_model() == "primary"


def test_get_active_model_default():
    from agent.model_layer import get_active_model
    assert get_active_model() == "primary"


# ---------------------------------------------------------------------------
# make_adk_model
# ---------------------------------------------------------------------------

def test_make_adk_model_returns_litellm_instance():
    from agent.model_layer import make_adk_model
    from google.adk.models.lite_llm import LiteLlm
    model = make_adk_model()
    assert isinstance(model, LiteLlm)


def test_make_adk_model_uses_primary_slug():
    from config.settings import settings
    from agent.model_layer import make_adk_model
    from google.adk.models.lite_llm import LiteLlm
    model = make_adk_model()
    assert model.model == settings.PRIMARY_MODEL


def test_make_adk_model_prefer_fallback():
    from config.settings import settings
    from agent.model_layer import make_adk_model
    model = make_adk_model(prefer_fallback=True)
    assert model.model == settings.FALLBACK_MODEL
