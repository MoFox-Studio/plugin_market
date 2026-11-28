"""GitHub Webhook 安全校验工具。"""

from __future__ import annotations

import hashlib
import hmac

from plugin_market_backend.errors import ApiError


def verify_github_signature(secret: str, body: bytes, signature: str | None) -> None:
    """配置密钥时校验 GitHub 的 X-Hub-Signature-256 请求头。"""
    if not secret:
        return
    if not signature or not signature.startswith("sha256="):
        raise ApiError(401, "INVALID_WEBHOOK_SIGNATURE", "必须提供 GitHub Webhook 签名。")
    expected = "sha256=" + hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, signature):
        raise ApiError(401, "INVALID_WEBHOOK_SIGNATURE", "GitHub Webhook 签名无效。")
