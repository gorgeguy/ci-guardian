"""GitHub webhook signature validation."""

import hashlib
import hmac
import logging

logger = logging.getLogger(__name__)


def validate_github_signature(payload: bytes, signature: str | None, secret: str) -> bool:
    """
    Validate GitHub webhook signature using HMAC SHA-256.

    Args:
        payload: The raw request body bytes
        signature: The X-Hub-Signature-256 header value
        secret: The webhook secret configured in GitHub

    Returns:
        True if the signature is valid, False otherwise
    """
    if not signature:
        logger.warning("Missing webhook signature")
        return False

    if not signature.startswith("sha256="):
        logger.warning("Invalid signature format - expected sha256= prefix")
        return False

    expected_signature = (
        "sha256="
        + hmac.new(
            secret.encode("utf-8"),
            payload,
            hashlib.sha256,
        ).hexdigest()
    )

    is_valid = hmac.compare_digest(expected_signature, signature)

    if not is_valid:
        logger.warning("Webhook signature validation failed")

    return is_valid
