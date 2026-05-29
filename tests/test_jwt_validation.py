"""Tests de validación JWT con JWKS (api.dependencies)."""

import asyncio
from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock, patch

import jwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import HTTPException

from api.dependencies import _decode_and_verify_supabase_jwt, get_current_user_id


def _generate_rsa_key():
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


def _public_pem(private_key) -> bytes:
    return private_key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )


def _make_rs256_token(private_key, **extra_claims) -> str:
    payload = {
        "sub": "supabase-user-123",
        "aud": "authenticated",
        "exp": datetime.now(UTC) + timedelta(hours=1),
        **extra_claims,
    }
    return jwt.encode(payload, private_key, algorithm="RS256")


def test_forged_jwt_invalid_signature_returns_401():
    """Token firmado con otra clave → verificación JWKS falla → 401."""
    signing_key = _generate_rsa_key()
    wrong_public_key = _generate_rsa_key()

    token = _make_rs256_token(signing_key)

    mock_signing_key = MagicMock()
    mock_signing_key.key = _public_pem(wrong_public_key)

    mock_client = MagicMock()
    mock_client.get_signing_key_from_jwt.return_value = mock_signing_key

    with patch("api.dependencies._get_jwks_client", return_value=mock_client):
        with pytest.raises(HTTPException) as exc_info:
            _decode_and_verify_supabase_jwt(token)

    assert exc_info.value.status_code == 401


def test_get_current_user_id_rejects_forged_jwt():
    signing_key = _generate_rsa_key()
    wrong_public_key = _generate_rsa_key()
    token = _make_rs256_token(signing_key)

    mock_signing_key = MagicMock()
    mock_signing_key.key = _public_pem(wrong_public_key)
    mock_client = MagicMock()
    mock_client.get_signing_key_from_jwt.return_value = mock_signing_key

    with patch("api.dependencies._get_jwks_client", return_value=mock_client):
        with pytest.raises(HTTPException) as exc_info:
            asyncio.run(get_current_user_id(authorization=f"Bearer {token}"))

    assert exc_info.value.status_code == 401


def test_valid_jwt_signature_returns_payload_sub():
    signing_key = _generate_rsa_key()
    token = _make_rs256_token(signing_key, sub="verified-subject")

    mock_signing_key = MagicMock()
    mock_signing_key.key = _public_pem(signing_key)
    mock_client = MagicMock()
    mock_client.get_signing_key_from_jwt.return_value = mock_signing_key

    with patch("api.dependencies._get_jwks_client", return_value=mock_client):
        payload = _decode_and_verify_supabase_jwt(token)

    assert payload["sub"] == "verified-subject"
