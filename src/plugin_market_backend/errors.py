"""Uniform API errors for the plugin market backend."""

from __future__ import annotations

from typing import Any

from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse


class ApiError(Exception):
    """Application error rendered as the market API error envelope."""

    def __init__(self, status_code: int, code: str, message: str, details: dict[str, Any] | None = None) -> None:
        """Create an API error."""

        self.status_code = status_code
        self.code = code
        self.message = message
        self.details = details or {}


def error_payload(code: str, message: str, details: dict[str, Any] | None = None) -> dict[str, Any]:
    """Build a uniform error envelope."""

    return {"error": {"code": code, "message": message, "details": details or {}}}


def _private_headers(request: Request) -> dict[str, str]:
    if request.url.path in {"/api/v1/recommendations", "/api/v1/me/recommendation-preferences"}:
        return {"Cache-Control": "private, no-store", "Vary": "Cookie, Authorization"}
    return {}


async def api_error_handler(request: Request, exc: ApiError) -> JSONResponse:
    """Render ApiError as JSON."""

    return JSONResponse(status_code=exc.status_code, content=error_payload(exc.code, exc.message, exc.details), headers=_private_headers(request))


async def validation_error_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    """Render request validation errors using the same envelope."""

    return JSONResponse(
        status_code=422,
        content=error_payload("VALIDATION_ERROR", "Request validation failed.", {"errors": jsonable_encoder(exc.errors())}),
        headers=_private_headers(request),
    )
