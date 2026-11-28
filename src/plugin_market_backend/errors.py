"""插件市场后端的统一 API 错误处理。"""

from __future__ import annotations

from typing import Any

from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse


class ApiError(Exception):
    """以市场 API 统一错误结构呈现的应用异常。"""

    def __init__(self, status_code: int, code: str, message: str, details: dict[str, Any] | None = None) -> None:
        """创建 API 错误。"""
        self.status_code = status_code
        self.code = code
        self.message = message
        self.details = details or {}


def error_payload(code: str, message: str, details: dict[str, Any] | None = None) -> dict[str, Any]:
    """构建统一的错误响应结构。"""
    return {"error": {"code": code, "message": message, "details": details or {}}}


def _private_headers(request: Request) -> dict[str, str]:
    if request.url.path in {"/api/v1/recommendations", "/api/v1/me/recommendation-preferences"}:
        return {"Cache-Control": "private, no-store", "Vary": "Cookie, Authorization"}
    return {}


async def api_error_handler(request: Request, exc: ApiError) -> JSONResponse:
    """将 ApiError 呈现为 JSON 响应。"""
    return JSONResponse(status_code=exc.status_code, content=error_payload(exc.code, exc.message, exc.details), headers=_private_headers(request))


async def validation_error_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    """使用统一结构呈现请求验证错误。"""
    return JSONResponse(
        status_code=422,
        content=error_payload("VALIDATION_ERROR", "请求验证失败。", {"errors": jsonable_encoder(exc.errors())}),
        headers=_private_headers(request),
    )
