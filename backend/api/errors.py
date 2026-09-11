"""RFC 7807 problem+json error handling (PRD §9)."""
from __future__ import annotations

import uuid

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException


def problem(status: int, title: str, detail: str, type_: str = "about:blank") -> JSONResponse:
    return JSONResponse(
        status_code=status,
        media_type="application/problem+json",
        content={"type": type_, "title": title, "status": status,
                 "detail": detail, "trace_id": uuid.uuid4().hex[:12]},
    )


def register_handlers(app: FastAPI) -> None:
    @app.exception_handler(StarletteHTTPException)
    async def _http(request: Request, exc: StarletteHTTPException):
        return problem(exc.status_code, exc.title or "HTTP Error",
                       str(exc.detail))

    @app.exception_handler(RequestValidationError)
    async def _validation(request: Request, exc: RequestValidationError):
        return problem(422, "Validation Error", str(exc.errors()[:5])[:1000])

    @app.exception_handler(Exception)
    async def _unhandled(request: Request, exc: Exception):  # pragma: no cover
        return problem(500, "Internal Server Error",
                       f"{type(exc).__name__}: {exc}", type_="internal-error")
