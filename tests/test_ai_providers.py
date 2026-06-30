"""Tests de la capa de providers de IA (0.2).

Sin red ni BD: usan un cliente OpenAI falso inyectado y monkeypatch sobre la
fachada `llm_client`. Verifican que el refactor preserva el comportamiento
(mismas firmas, mismos parámetros hacia el modelo) y que el factory selecciona
el modelo correcto por tier.
"""

from __future__ import annotations

import types

from process_ai_core.ai.openai_provider import OpenAIProvider


# --- cliente OpenAI falso -------------------------------------------------

class _FakeMessage:
    def __init__(self, content):
        self.content = content


class _FakeChoice:
    def __init__(self, content):
        self.message = _FakeMessage(content)


class _FakeCompletion:
    def __init__(self, content):
        self.choices = [_FakeChoice(content)]


class _FakeCompletions:
    def __init__(self, content):
        self._content = content
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return _FakeCompletion(self._content)


class _FakeChat:
    def __init__(self, content):
        self.completions = _FakeCompletions(content)


class _FakeOpenAI:
    def __init__(self, content='{"ok": true}'):
        self.chat = _FakeChat(content)


# --- OpenAIProvider.complete_json ----------------------------------------

def test_complete_json_passes_expected_params():
    fake = _FakeOpenAI('{"ok": true}')
    p = OpenAIProvider(api_key="x", model_text="m-test", client=fake)

    out = p.complete_json(system="S", user="U", temperature=0.3)

    assert out == '{"ok": true}'
    kw = fake.chat.completions.calls[0]
    assert kw["model"] == "m-test"
    assert kw["temperature"] == 0.3
    assert kw["response_format"] == {"type": "json_object"}
    assert kw["messages"] == [
        {"role": "system", "content": "S"},
        {"role": "user", "content": "U"},
    ]


def test_complete_json_defaults_empty_object():
    fake = _FakeOpenAI(None)  # modelo devuelve content=None
    p = OpenAIProvider(api_key="x", model_text="m", client=fake)
    assert p.complete_json(system="s", user="u") == "{}"


# --- fachada llm_client delega en los providers ---------------------------

def test_generate_document_json_delegates(monkeypatch):
    import process_ai_core.llm_client as lc

    captured = {}

    class _Stub:
        def complete_json(self, *, system, user, temperature):
            captured.update(system=system, user=user, temperature=temperature)
            return '{"x": 1}'

    monkeypatch.setattr(lc, "get_llm_provider", lambda tier="strong": _Stub())

    out = lc.generate_document_json("BODY", "SYS", temperature=0.5)

    assert out == '{"x": 1}'
    assert captured["system"] == "SYS"
    assert captured["user"].endswith("BODY")
    assert captured["temperature"] == 0.5


def test_select_best_frame_delegates(monkeypatch):
    import process_ai_core.llm_client as lc

    captured = {}

    class _Stub:
        def pick_frame(self, *, step_summary, image_paths, model=None):
            captured.update(step_summary=step_summary, image_paths=image_paths, model=model)
            return {"selected_index": 0, "title": "t", "notes": ""}

    monkeypatch.setattr(lc, "get_vision_provider", lambda: _Stub())

    out = lc.select_best_frame_for_step("paso", ["a.png"], model="mv")

    assert out == {"selected_index": 0, "title": "t", "notes": ""}
    assert captured == {"step_summary": "paso", "image_paths": ["a.png"], "model": "mv"}


# --- factory: selección de modelo por tier --------------------------------

def _settings(text="strong-m", cheap=""):
    return types.SimpleNamespace(
        openai_api_key="",
        openai_model_text=text,
        openai_model_text_cheap=cheap,
        openai_model_transcribe="t",
        openai_model_transcribe_timestamps="w",
    )


def test_factory_cheap_falls_back_to_strong(monkeypatch):
    from process_ai_core.ai import factory
    from process_ai_core.ai import openai_provider as op

    monkeypatch.setattr(factory, "get_settings", lambda: _settings(text="strong-m", cheap=""))
    monkeypatch.setattr(op, "get_settings", lambda: _settings(text="strong-m", cheap=""))

    assert factory.get_llm_provider("strong")._model_text == "strong-m"
    assert factory.get_llm_provider("cheap")._model_text == "strong-m"  # fallback


def test_factory_cheap_uses_cheap_when_set(monkeypatch):
    from process_ai_core.ai import factory
    from process_ai_core.ai import openai_provider as op

    monkeypatch.setattr(factory, "get_settings", lambda: _settings(text="strong-m", cheap="cheap-m"))
    monkeypatch.setattr(op, "get_settings", lambda: _settings(text="strong-m", cheap="cheap-m"))

    assert factory.get_llm_provider("strong")._model_text == "strong-m"
    assert factory.get_llm_provider("cheap")._model_text == "cheap-m"
