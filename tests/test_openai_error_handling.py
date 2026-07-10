"""Manejo de errores de OpenAI (Etapa 3 MVP).

- El cliente se construye con timeout y max_retries desde settings (el SDK reintenta
  con backoff ante rate-limit/5xx/timeout/conexión).
- Un error del SDK que sobrevive a los reintentos se traduce a AIProviderError,
  claro y logueado, en vez de propagar un traceback opaco del SDK.
"""

from __future__ import annotations

import pytest
from openai import OpenAIError

from process_ai_core.ai.openai_provider import AIProviderError, OpenAIProvider


class _BoomChat:
    class completions:
        @staticmethod
        def create(*a, **k):
            raise OpenAIError("rate limit / timeout simulado")


class _BoomClient:
    """Cliente falso cuyo chat.completions.create siempre falla como el SDK."""
    chat = _BoomChat()


def test_error_del_sdk_se_traduce_a_aiprovidererror():
    provider = OpenAIProvider(api_key="sk-test", client=_BoomClient())
    with pytest.raises(AIProviderError) as exc:
        provider.complete_json(system="s", user="u")
    # El mensaje nombra la operación y el tipo de error subyacente (diagnosticable).
    assert "complete_json" in str(exc.value)
    assert "OpenAIError" in str(exc.value)
    # Encadena la excepción original del SDK.
    assert isinstance(exc.value.__cause__, OpenAIError)


def test_cliente_real_se_construye_con_timeout_y_retries(monkeypatch):
    captured = {}

    class _FakeOpenAI:
        def __init__(self, *, api_key, timeout, max_retries):
            captured["timeout"] = timeout
            captured["max_retries"] = max_retries

    monkeypatch.setattr("process_ai_core.ai.openai_provider.OpenAI", _FakeOpenAI)

    provider = OpenAIProvider(api_key="sk-test")
    _ = provider.client  # fuerza la construcción lazy

    from process_ai_core.config import get_settings

    settings = get_settings()
    assert captured["timeout"] == settings.openai_timeout_seconds
    assert captured["max_retries"] == settings.openai_max_retries
