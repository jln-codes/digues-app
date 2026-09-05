FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY webapp/pyproject.toml ./webapp/
COPY webapp/backend ./webapp/backend
COPY webapp/frontend ./webapp/frontend

RUN python -m pip install --upgrade pip \
    && python -m pip install ./webapp \
    && useradd --create-home --uid 10001 --shell /usr/sbin/nologin appuser

USER appuser

EXPOSE 8000

CMD ["python", "-m", "uvicorn", "--app-dir", "webapp/backend", "digues_webapp.app:app", "--host", "0.0.0.0", "--port", "8000"]
