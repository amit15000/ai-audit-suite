"""Celery tasks for async comparison processing."""
from __future__ import annotations

from celery import Celery

from app.core.config import get_settings
from app.core.database import get_session_factory
from app.domain.models import Comparison
from app.services.comparison.comparison_service import process_comparison

settings = get_settings()

celery_app = Celery(
    "ai_audit",
    broker=settings.celery.broker_url,
    backend=settings.celery.result_backend,
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
)


@celery_app.task(name="process_comparison")
def process_comparison_task(comparison_id: str) -> None:
    """Process comparison asynchronously."""
    import asyncio
    
    session_factory = get_session_factory()
    db = session_factory()
    
    try:
        comparison = db.query(Comparison).filter(Comparison.id == comparison_id).first()
        if comparison:
            # Run async function in sync context
            asyncio.run(process_comparison(db, comparison))
    finally:
        db.close()

