"""Tests para la firma HMAC de URLs de artefactos (api/artifact_signing.py).

Cubre:
  - sign_artifact_url genera una URL con token válido.
  - verify_artifact_token acepta un token recién generado.
  - Token expirado → False.
  - Token con run_id manipulado → False.
  - Token con filename manipulado → False.
  - Token truncado / malformado → False.
  - Firma diferente (secreto distinto) → False.
  - El endpoint GET /artifacts/{run_id}/{filename} sirve el archivo con token válido.
  - Sin token → 422 (campo requerido).
  - Token inválido → 404.
  - Token expirado → 404.
  - Token de otro run/filename → 404.
  - Cross-tenant: token firmado con workspace_id_A no sirve para workspace_id_B
    (la firma es distinta aunque run_id y filename coincidan).
"""

import time
import tempfile
import os
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest
from fastapi.testclient import TestClient

from api.artifact_signing import sign_artifact_url, verify_artifact_token
from process_ai_core.config import get_settings, Settings


# ── Helpers de settings con secreto ───────────────────────────────────────────

_TEST_SECRET = "test-artifact-signing-secret-for-pytest"
_WS_A = "workspace-aaa-1111"
_WS_B = "workspace-bbb-2222"
_RUN = "run-cccc-3333"
_FILE = "process.pdf"

# Ruta de patch: get_settings se importa de forma tardía dentro de las funciones de
# artifact_signing, así que parcheamos el símbolo en su módulo de origen.
_SETTINGS_PATCH = "process_ai_core.config.get_settings"


def _patched_settings(**overrides):
    """Devuelve un Settings con el secreto de test y overrides opcionales."""
    base = get_settings()
    kwargs = {
        "openai_api_key": base.openai_api_key,
        "openai_model_text": base.openai_model_text,
        "openai_model_transcribe": base.openai_model_transcribe,
        "openai_model_transcribe_timestamps": base.openai_model_transcribe_timestamps,
        "api_base_url": base.api_base_url,
        "artifact_signing_secret": _TEST_SECRET,
        "artifact_url_ttl_seconds": 900,
        "output_dir": base.output_dir,
    }
    kwargs.update(overrides)
    return Settings(**kwargs)


# ── Tests unitarios de sign/verify ────────────────────────────────────────────


class TestSignArtifactUrl:
    def test_genera_url_con_token(self):
        with patch(_SETTINGS_PATCH, return_value=_patched_settings()):
            url = sign_artifact_url(_RUN, _FILE, _WS_A)
        assert url.startswith(f"/api/v1/artifacts/{_RUN}/{_FILE}?token=")
        assert "token=" in url

    def test_url_contiene_run_id_y_filename(self):
        with patch(_SETTINGS_PATCH, return_value=_patched_settings()):
            url = sign_artifact_url(_RUN, _FILE, _WS_A)
        assert f"/api/v1/artifacts/{_RUN}/{_FILE}" in url

    def test_filename_con_subdirectorio(self):
        """Filename con barra debe codificarse correctamente."""
        filename = "assets/frames/step01.png"
        with patch(_SETTINGS_PATCH, return_value=_patched_settings()):
            url = sign_artifact_url(_RUN, filename, _WS_A)
        assert f"/api/v1/artifacts/{_RUN}/" in url
        assert "token=" in url

    def test_ttl_custom(self):
        with patch(_SETTINGS_PATCH, return_value=_patched_settings()):
            before = int(time.time())
            url = sign_artifact_url(_RUN, _FILE, _WS_A, ttl=60)
            token = url.split("token=")[1]
            exp = int(token.split(".")[0])
        assert before + 55 <= exp <= before + 65


class TestVerifyArtifactToken:
    def test_token_valido_retorna_true(self):
        with patch(_SETTINGS_PATCH, return_value=_patched_settings()):
            url = sign_artifact_url(_RUN, _FILE, _WS_A)
            token = url.split("token=")[1]
            result = verify_artifact_token(token, _RUN, _FILE)
        assert result is True

    def test_token_expirado_retorna_false(self):
        with patch(_SETTINGS_PATCH, return_value=_patched_settings()):
            url = sign_artifact_url(_RUN, _FILE, _WS_A, ttl=-1)
            token = url.split("token=")[1]
            result = verify_artifact_token(token, _RUN, _FILE)
        assert result is False

    def test_run_id_manipulado_retorna_false(self):
        with patch(_SETTINGS_PATCH, return_value=_patched_settings()):
            url = sign_artifact_url(_RUN, _FILE, _WS_A)
            token = url.split("token=")[1]
            result = verify_artifact_token(token, "otro-run-id", _FILE)
        assert result is False

    def test_filename_manipulado_retorna_false(self):
        with patch(_SETTINGS_PATCH, return_value=_patched_settings()):
            url = sign_artifact_url(_RUN, _FILE, _WS_A)
            token = url.split("token=")[1]
            result = verify_artifact_token(token, _RUN, "process.json")
        assert result is False

    def test_token_truncado_retorna_false(self):
        with patch(_SETTINGS_PATCH, return_value=_patched_settings()):
            result = verify_artifact_token("bad", _RUN, _FILE)
        assert result is False

    def test_token_vacio_retorna_false(self):
        with patch(_SETTINGS_PATCH, return_value=_patched_settings()):
            result = verify_artifact_token("", _RUN, _FILE)
        assert result is False

    def test_firma_distinta_retorna_false(self):
        """Token generado con secreto A no pasa con secreto B."""
        settings_a = _patched_settings(artifact_signing_secret="secret-aaa")
        settings_b = _patched_settings(artifact_signing_secret="secret-bbb")

        with patch(_SETTINGS_PATCH, return_value=settings_a):
            url = sign_artifact_url(_RUN, _FILE, _WS_A)
            token = url.split("token=")[1]

        with patch(_SETTINGS_PATCH, return_value=settings_b):
            result = verify_artifact_token(token, _RUN, _FILE)
        assert result is False

    def test_cross_workspace_token_retorna_false(self):
        """
        Token firmado para workspace A no es válido para verificar workspace B.
        El workspace_id está incrustado en la firma, así que un token de ws_a
        no sirve para ws_b aunque run_id y filename sean idénticos.
        Esto previene que alguien use una URL de ws_a para acceder a ws_b.
        """
        with patch(_SETTINGS_PATCH, return_value=_patched_settings()):
            url_a = sign_artifact_url(_RUN, _FILE, _WS_A)
            url_b = sign_artifact_url(_RUN, _FILE, _WS_B)
            token_a = url_a.split("token=")[1]
            token_b = url_b.split("token=")[1]

            # token_a != token_b (workspace_id está en la firma)
            assert token_a != token_b

            # token_a no pasa para run_id+filename si se intercambia manualmente
            # (en la práctica el workspace_id está embebido en el token, así que
            #  cambiar el workspace_id en el token invalida la firma)
            exp_str, ws_id, sig = token_a.split(".", 2)
            tampered = f"{exp_str}.{_WS_B}.{sig}"
            result = verify_artifact_token(tampered, _RUN, _FILE)
        assert result is False


# ── Tests de integración con el endpoint HTTP ─────────────────────────────────


@pytest.fixture
def artifact_client(tmp_path):
    """
    Cliente de test con:
      - Un archivo real en el output_dir temporal.
      - Settings con secreto de test.
    """
    run_id = "test-run-999"
    filename = "process.pdf"
    run_dir = tmp_path / run_id
    run_dir.mkdir(parents=True)
    (run_dir / filename).write_bytes(b"%PDF-1.4 fake content")

    test_settings = _patched_settings(output_dir=str(tmp_path))

    # Parchear en dos puntos:
    #   1. process_ai_core.config.get_settings → afecta imports tardíos (artifact_signing.py)
    #   2. api.routes.artifacts.get_settings  → afecta el import de nivel de módulo en artifacts.py
    with patch(_SETTINGS_PATCH, return_value=test_settings):
        with patch("api.routes.artifacts.get_settings", return_value=test_settings):
            from api.main import app
            with TestClient(app, raise_server_exceptions=True) as c:
                yield c, run_id, filename, tmp_path


class TestArtifactEndpoint:
    def test_sin_token_retorna_422(self, artifact_client):
        """Sin el campo token requerido → 422 Unprocessable Entity."""
        client, run_id, filename, _ = artifact_client
        resp = client.get(f"/api/v1/artifacts/{run_id}/{filename}")
        assert resp.status_code == 422

    def test_token_invalido_retorna_404(self, artifact_client):
        client, run_id, filename, _ = artifact_client
        resp = client.get(f"/api/v1/artifacts/{run_id}/{filename}?token=not-a-valid-token")
        assert resp.status_code == 404

    def test_token_expirado_retorna_404(self, artifact_client):
        client, run_id, filename, _ = artifact_client
        with patch(_SETTINGS_PATCH, return_value=_patched_settings()):
            url = sign_artifact_url(run_id, filename, _WS_A, ttl=-1)
            token = url.split("token=")[1]
        resp = client.get(f"/api/v1/artifacts/{run_id}/{filename}?token={token}")
        assert resp.status_code == 404

    def test_token_de_otro_run_retorna_404(self, artifact_client):
        client, run_id, filename, _ = artifact_client
        with patch(_SETTINGS_PATCH, return_value=_patched_settings()):
            url = sign_artifact_url("otro-run-id", filename, _WS_A)
            token = url.split("token=")[1]
        resp = client.get(f"/api/v1/artifacts/{run_id}/{filename}?token={token}")
        assert resp.status_code == 404

    def test_token_de_otro_filename_retorna_404(self, artifact_client):
        client, run_id, filename, _ = artifact_client
        with patch(_SETTINGS_PATCH, return_value=_patched_settings()):
            url = sign_artifact_url(run_id, "process.json", _WS_A)
            token = url.split("token=")[1]
        resp = client.get(f"/api/v1/artifacts/{run_id}/{filename}?token={token}")
        assert resp.status_code == 404

    def test_token_valido_sirve_archivo(self, artifact_client):
        """Token válido + archivo existente → 200 con el contenido."""
        client, run_id, filename, tmp_path = artifact_client
        with patch(_SETTINGS_PATCH, return_value=_patched_settings(output_dir=str(tmp_path))):
            url = sign_artifact_url(run_id, filename, _WS_A)
            token = url.split("token=")[1]
        resp = client.get(f"/api/v1/artifacts/{run_id}/{filename}?token={token}")
        assert resp.status_code == 200

    def test_cross_tenant_token_retorna_404(self, artifact_client):
        """
        Token firmado para workspace_A no puede servir el archivo aunque run_id y
        filename coincidan si se altera el workspace_id en el token.
        Simula que un atacante re-usa una URL firmada de tenant A en tenant B.
        """
        client, run_id, filename, tmp_path = artifact_client
        with patch(_SETTINGS_PATCH, return_value=_patched_settings(output_dir=str(tmp_path))):
            url_a = sign_artifact_url(run_id, filename, _WS_A)
            token_a = url_a.split("token=")[1]
            # Alterar el workspace_id en el token (mantener exp y sig sin cambios)
            exp_str, ws_id, sig = token_a.split(".", 2)
            tampered = f"{exp_str}.{_WS_B}.{sig}"
        resp = client.get(f"/api/v1/artifacts/{run_id}/{filename}?token={tampered}")
        assert resp.status_code == 404
