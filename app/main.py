from __future__ import annotations

import logging
from typing import Any, Dict

import structlog
from fastapi import Depends, FastAPI, Request, Response, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

from app.api.v1.routers import auth, comparison, multi_llm, responses, similarity, ui
from app.core import configure_logging, get_settings
from app.core.config import AppSettings
from app.domain.schemas import AuditRequest, AuditResponse
from app.services.comparison.audit_service import AuditService
from app.adapters import mock as _mock_adapter  # noqa: F401
from app.adapters import openai as _openai_adapter  # noqa: F401
from app.adapters import gemini as _gemini_adapter  # noqa: F401
from app.adapters import groq as _groq_adapter  # noqa: F401
from app.adapters import huggingface as _huggingface_adapter  # noqa: F401


def create_app(settings: AppSettings) -> FastAPI:
    configure_logging(settings.log_level)
    app = FastAPI(title="Project W Audit API", version="0.1.0")
    
    # Global exception handler for unhandled exceptions
    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        """Handle all unhandled exceptions and return proper JSON response."""
        import structlog
        logger = structlog.get_logger(__name__)
        logger.error("unhandled_exception", error=str(exc), exc_info=True)
        
        error_message = str(exc)
        error_code = "INTERNAL_ERROR"
        
        # Provide helpful messages for common errors
        if "API key" in error_message or "not configured" in error_message:
            error_code = "API_KEY_MISSING"
            error_message = (
                "OpenAI API key is required for embedding generation. "
                "Please set OPENAI_API_KEY or ADAPTER_OPENAI_API_KEY in your .env file "
                "and restart the server."
            )
        
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "success": False,
                "error": {
                    "code": error_code,
                    "message": error_message,
                },
            },
        )
    
    # CORS configuration
    cors_origins = settings.cors_origins if hasattr(settings, "cors_origins") else ["*"]
    # Handle wildcard origin - can't use credentials with "*"
    allow_credentials = "*" not in cors_origins
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins,
        allow_credentials=allow_credentials,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # Root endpoint - define early to ensure it takes precedence
    @app.get("/", tags=["root"])
    def root() -> Dict[str, Any]:
        """Root endpoint to verify backend is running and get API information."""
        return {
            "status": "running",
            "message": "AI Audit Backend API is running",
            "version": "0.1.0",
            "endpoints": {
                "health": "/health",
                "metrics": "/metrics",
                "docs": "/docs",
                "api": "/api/v1",
                "auth": "/api/v1/auth",
                "comparison": "/api/v1/comparison",
                "responses": "/api/v1/responses"
            },
            "cors_enabled": True,
            "cors_origins": cors_origins if "*" not in cors_origins else ["* (all origins)"]
        }
    
    service = AuditService()

    # Include API routers
    app.include_router(auth.router)
    app.include_router(comparison.router)
    app.include_router(multi_llm.router)
    app.include_router(responses.router)
    app.include_router(similarity.router)
    app.include_router(ui.router)

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

