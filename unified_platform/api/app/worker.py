from __future__ import annotations

from celery import Celery

from app.core.config import settings

celery_app = Celery("unified_erp", broker=settings.redis_url, backend=settings.redis_url)


@celery_app.task(name="health.ping")
def health_ping() -> str:
    return "pong"
