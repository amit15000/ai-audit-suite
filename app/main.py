from __future__ import annotations

import logging
from typing import Any, Dict

import structlog
from fastapi import Depends, FastAPI, Response, status
from fastapi.middleware.cors import CORSMiddleware
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

from app.api.v1.routers import multi_llm
from app.core import configure_logging, get_settings
from app.core.config import AppSettings
from app.domain.schemas import AuditRequest, AuditResponse
from app.services.audit_service import AuditService
from app.adapters import mock as _mock_adapter  # noqa: F401
from app.adapters import openai as _openai_adapter  # noqa: F401
from app.adapters import gemini as _gemini_adapter  # noqa: F401


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

    # Include API routers
    app.include_router(multi_llm.router)

    @app.post("/audit", response_model=AuditResponse)
    async def audit_endpoint(request: AuditRequest) -> AuditResponse:
        return await service.execute_async(request)

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

