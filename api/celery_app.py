import os
from celery import Celery

REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")

celery_app = Celery(
    "cruxcam",
    broker=REDIS_URL,
    backend=REDIS_URL,
    include=["api.tasks"],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    result_expires=3600,
    worker_prefetch_multiplier=1,   # one task at a time per worker (video processing is heavy)
    task_acks_late=True,            # ack only after task completes, so crashes don't lose jobs
)
