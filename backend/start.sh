#!/bin/sh
set -e

case "${ROLE:-api}" in
  worker)
    exec celery -A app.tasks worker --loglevel=info
    ;;
  beat)
    exec celery -A app.tasks beat --loglevel=info
    ;;
  api)
    alembic upgrade head
    exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}"
    ;;
  *)
    echo "Unknown ROLE=${ROLE}" >&2
    exit 1
    ;;
esac
