#!/bin/sh
# Start Celery worker in background, then run uvicorn in foreground.
# Railway (and any OCI host) routes HTTP to $PORT — uvicorn as PID 1 ensures
# clean shutdown signals propagate correctly.
celery -A api.celery_app worker --loglevel=info --pool=solo &
exec uvicorn api.main:app --host 0.0.0.0 --port "${PORT:-8000}"
