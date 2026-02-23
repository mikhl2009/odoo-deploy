from __future__ import annotations

from celery import Celery

from app.core.config import settings

celery_app = Celery("unified_erp", broker=settings.redis_url, backend=settings.redis_url)

# ---------------------------------------------------------------------------
# Beat schedules
# ---------------------------------------------------------------------------

celery_app.conf.beat_schedule = {
    "wgr-poll-stock": {
        "task": "app.tasks.wgr.poll_stock",
        "schedule": 300,  # every 5 minutes
    },
    "wgr-poll-orders": {
        "task": "app.tasks.wgr.poll_orders",
        "schedule": 120,  # every 2 minutes
    },
    "woo-push-stock": {
        "task": "app.tasks.woo.push_stock",
        "schedule": 30,  # every 30 seconds
    },
    "nshift-process-queue": {
        "task": "app.tasks.nshift.process_queue",
        "schedule": 15,  # every 15 seconds
    },
}

# ---------------------------------------------------------------------------
# Queue routing
# ---------------------------------------------------------------------------

celery_app.conf.task_routes = {
    "app.tasks.wgr.*": {"queue": "wgr"},
    "app.tasks.woo.*": {"queue": "woo"},
    "app.tasks.nshift.*": {"queue": "nshift"},
}

# ---------------------------------------------------------------------------
# Legacy health task
# ---------------------------------------------------------------------------


@celery_app.task(name="health.ping")
def health_ping() -> str:
    return "pong"
