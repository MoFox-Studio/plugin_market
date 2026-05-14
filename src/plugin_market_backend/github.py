"""GitHub webhook security helpers."""

from __future__ import annotations

import hashlib
import hmac

from plugin_market_backend.errors import ApiError


def verify_github_signature(secret: str, body: bytes, signature: str | None) -> None:
    """Validate GitHub's X-Hub-Signature-256 header when a secret is configured."""

    if not secret:
        return
    if not signature or not signature.startswith("sha256="):
        raise ApiError(401, "INVALID_WEBHOOK_SIGNATURE", "GitHub webhook signature is required.")
    expected = "sha256=" + hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, signature):
        raise ApiError(401, "INVALID_WEBHOOK_SIGNATURE", "GitHub webhook signature is invalid.")
