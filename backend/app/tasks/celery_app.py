from celery import Celery
from celery.schedules import crontab
from app.core.config import settings

celery_app = Celery(
    "consensus",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
    include=[
        "app.tasks.ingestion_tasks",
        "app.tasks.scoring_tasks",
        "app.tasks.snapshot_tasks",
        "app.tasks.alert_tasks",
    ],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    beat_schedule={
        "daily-data-integrity-monitor": {
            "task": "app.tasks.alerts.run_data_integrity_monitoring",
            "schedule": crontab(minute=15, hour=1),
        },
    },
)
