from __future__ import annotations

import logging
from typing import Any, Dict

import structlog
from fastapi import Depends, FastAPI, Response, status
from fastapi.middleware.cors import CORSMiddleware
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

from app.config import AppSettings, get_settings
from app.models import AuditRequest, AuditResponse
from app.services.audit_service import AuditService
from app.adapters import mock as _mock_adapter  # noqa: F401


def configure_logging(level: str) -> None:
    numeric_level = getattr(logging, level.upper(), logging.INFO)
    logging.basicConfig(level=numeric_level)
    structlog.configure(
        wrapper_class=structlog.make_filtering_bound_logger(numeric_level),
        processors=[structlog.processors.JSONRenderer()],
    )


def create_app(settings: AppSettings) -> FastAPI:
    configure_logging(settings.log_level)
    app = FastAPI(title="Project W Audit API", version="0.1.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    service = AuditService()

    @app.post("/audit", response_model=AuditResponse)
    def audit_endpoint(request: AuditRequest) -> AuditResponse:
        return service.execute(request)

    @app.get("/health")
    def health() -> Dict[str, Any]:
        return {"status": "ok"}

    @app.get("/metrics")
    def metrics() -> Response:
        data = generate_latest()
        return Response(content=data, media_type=CONTENT_TYPE_LATEST)

    return app


def get_app(settings: AppSettings = Depends(get_settings)) -> FastAPI:
    return create_app(settings)


settings = get_settings()
app = create_app(settings)

