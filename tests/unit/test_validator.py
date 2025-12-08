"""Tests for webhook signature validation."""

import hashlib
import hmac

from ci_guardian.webhook.validator import validate_github_signature


def test_validate_valid_signature():
    """Test that valid signatures are accepted."""
    secret = "test-secret-123"
    payload = b'{"action": "completed"}'

    # Generate valid signature
    signature = (
        "sha256="
        + hmac.new(
            secret.encode("utf-8"),
            payload,
            hashlib.sha256,
        ).hexdigest()
    )

    assert validate_github_signature(payload, signature, secret) is True


def test_validate_invalid_signature():
    """Test that invalid signatures are rejected."""
    secret = "test-secret-123"
    payload = b'{"action": "completed"}'
    invalid_signature = "sha256=" + "a" * 64

    assert validate_github_signature(payload, invalid_signature, secret) is False


def test_validate_missing_signature():
    """Test that missing signatures are rejected."""
    secret = "test-secret-123"
    payload = b'{"action": "completed"}'

    assert validate_github_signature(payload, None, secret) is False


def test_validate_wrong_prefix():
    """Test that signatures with wrong prefix are rejected."""
    secret = "test-secret-123"
    payload = b'{"action": "completed"}'
    signature = (
        "sha1="
        + hmac.new(
            secret.encode("utf-8"),
            payload,
            hashlib.sha256,
        ).hexdigest()
    )

    assert validate_github_signature(payload, signature, secret) is False


def test_validate_different_payload():
    """Test that signatures for different payloads are rejected."""
    secret = "test-secret-123"
    payload1 = b'{"action": "completed"}'
    payload2 = b'{"action": "started"}'

    signature = (
        "sha256="
        + hmac.new(
            secret.encode("utf-8"),
            payload1,
            hashlib.sha256,
        ).hexdigest()
    )

    assert validate_github_signature(payload2, signature, secret) is False
