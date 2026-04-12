# Run all processes with: honcho start (pip install honcho)
# Or run individually in separate terminals.
#
# Windows note: Celery uses --pool=solo because prefork doesn't work on Windows.
web: cd backend && uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
worker: cd backend && uv run celery -A app.tasks.celery_app.celery_app worker --loglevel=info --pool=solo
beat: cd backend && uv run celery -A app.tasks.celery_app.celery_app beat --loglevel=info
