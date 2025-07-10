"""
Celery application for MEISTROVERSE background task processing
"""

from celery import Celery
from meistroverse.config import settings

# Create Celery app
celery_app = Celery(
    "meistroverse",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
    include=[
        "meistroverse.tasks.analysis_tasks",
        "meistroverse.tasks.maintenance_tasks",
        "meistroverse.tasks.notification_tasks"
    ]
)

# Configuration
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=30 * 60,  # 30 minutes
    task_soft_time_limit=25 * 60,  # 25 minutes
    worker_prefetch_multiplier=1,
    worker_max_tasks_per_child=1000,
)

# Periodic tasks configuration
celery_app.conf.beat_schedule = {
    "daily-analysis": {
        "task": "meistroverse.tasks.analysis_tasks.run_daily_analysis",
        "schedule": 60.0 * 60.0 * 24.0,  # Daily
        "options": {"queue": "analysis"}
    },
    "cleanup-old-logs": {
        "task": "meistroverse.tasks.maintenance_tasks.cleanup_old_logs",
        "schedule": 60.0 * 60.0 * 6.0,  # Every 6 hours
        "options": {"queue": "maintenance"}
    },
    "rebuild-knowledge-index": {
        "task": "meistroverse.tasks.maintenance_tasks.rebuild_knowledge_index",
        "schedule": 60.0 * 60.0 * 24.0 * 7.0,  # Weekly
        "options": {"queue": "maintenance"}
    }
}

# Queue routing
celery_app.conf.task_routes = {
    "meistroverse.tasks.analysis_tasks.*": {"queue": "analysis"},
    "meistroverse.tasks.maintenance_tasks.*": {"queue": "maintenance"},
    "meistroverse.tasks.notification_tasks.*": {"queue": "notifications"},
}