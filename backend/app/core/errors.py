import logging
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from slowapi.errors import RateLimitExceeded
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.logging import request_id_context

logger = logging.getLogger("clinic-api")


class ApiError(Exception):
    def __init__(
        self,
        status_code: int,
        code: str,
        message: str,
        *,
        details: Any = None,
        headers: dict[str, str] | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message
        self.details = details
        self.headers = headers


def _request_id(request: Request) -> str:
    return getattr(request.state, "request_id", "") or request_id_context.get()


def error_response(
    request: Request,
    *,
    status_code: int,
    code: str,
    message: str,
    details: Any = None,
    headers: dict[str, str] | None = None,
) -> JSONResponse:
    request_id = _request_id(request)
    body = {
        "detail": message,
        "error": {
            "code": code,
            "message": message,
            "details": details,
            "request_id": request_id or None,
        },
    }
    if request_id:
        headers = {**(headers or {}), "X-Request-ID": request_id}
    return JSONResponse(
        status_code=status_code,
        content=body,
        headers=headers,
    )


def _detail_message(detail: Any) -> str:
    if isinstance(detail, str):
        return detail
    if isinstance(detail, list):
        messages = [
            item.get("msg", str(item)) if isinstance(item, dict) else str(item)
            for item in detail
        ]
        return "; ".join(messages) or "Request failed"
    if isinstance(detail, dict):
        return str(detail.get("message") or detail.get("detail") or detail)
    return str(detail)


async def api_error_handler(request: Request, exc: ApiError) -> JSONResponse:
    return error_response(
        request,
        status_code=exc.status_code,
        code=exc.code,
        message=exc.message,
        details=exc.details,
        headers=exc.headers,
    )


async def http_error_handler(
    request: Request, exc: StarletteHTTPException
) -> JSONResponse:
    message = _detail_message(exc.detail)
    code = {
        400: "BAD_REQUEST",
        401: "UNAUTHORIZED",
        403: "FORBIDDEN",
        404: "NOT_FOUND",
        409: "CONFLICT",
        429: "RATE_LIMITED",
        503: "SERVICE_UNAVAILABLE",
    }.get(exc.status_code, "HTTP_ERROR")
    return error_response(
        request,
        status_code=exc.status_code,
        code=code,
        message=message,
        headers=dict(exc.headers or {}),
    )


async def validation_error_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    details = [
        {
            "location": list(error.get("loc", [])),
            "message": error.get("msg", "Invalid value"),
            "type": error.get("type", "value_error"),
        }
        for error in exc.errors()
    ]
    message = details[0]["message"] if details else "Request validation failed"
    return error_response(
        request,
        status_code=422,
        code="VALIDATION_ERROR",
        message=message,
        details=details,
    )


async def rate_limit_handler(
    request: Request, exc: RateLimitExceeded
) -> JSONResponse:
    return error_response(
        request,
        status_code=429,
        code="RATE_LIMITED",
        message="Too many requests. Please try again shortly.",
    )


async def unhandled_error_handler(
    request: Request, exc: Exception
) -> JSONResponse:
    logger.error(
        "unhandled_api_error",
        extra={
            "method": request.method,
            "path": request.url.path,
        },
        exc_info=(type(exc), exc, exc.__traceback__),
    )
    return error_response(
        request,
        status_code=500,
        code="INTERNAL_ERROR",
        message="An unexpected error occurred.",
    )


def register_error_handlers(app: FastAPI) -> None:
    app.add_exception_handler(ApiError, api_error_handler)
    app.add_exception_handler(StarletteHTTPException, http_error_handler)
    app.add_exception_handler(RequestValidationError, validation_error_handler)
    app.add_exception_handler(RateLimitExceeded, rate_limit_handler)
    app.add_exception_handler(Exception, unhandled_error_handler)
