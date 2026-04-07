# syntax=docker/dockerfile:1

ARG PYTHON_IMAGE=python:3.12-slim

FROM ${PYTHON_IMAGE} AS build

ARG APT_MIRROR_HOST=""
ARG PIP_INDEX_URL=""

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/backend \
    VIRTUAL_ENV=/opt/venv \
    PATH=/opt/venv/bin:$PATH

WORKDIR /backend

RUN set -eux; \
    if [ -n "$APT_MIRROR_HOST" ]; then \
        if [ -f /etc/apt/sources.list.d/debian.sources ]; then \
            sed -i "s|deb.debian.org|$APT_MIRROR_HOST|g" /etc/apt/sources.list.d/debian.sources; \
        elif [ -f /etc/apt/sources.list ]; then \
            sed -i "s|deb.debian.org|$APT_MIRROR_HOST|g" /etc/apt/sources.list; \
        fi; \
    fi; \
    apt-get update; \
    apt-get install -y --no-install-recommends gcc; \
    rm -rf /var/lib/apt/lists/*

RUN python -m venv "$VIRTUAL_ENV"

COPY app/requirements-runtime.txt /backend/requirements-runtime.txt

RUN set -eux; \
    if [ -n "$PIP_INDEX_URL" ]; then \
        python -m pip install --no-cache-dir --upgrade pip -i "$PIP_INDEX_URL"; \
    else \
        python -m pip install --no-cache-dir --upgrade pip; \
    fi; \
    if [ -n "$PIP_INDEX_URL" ]; then \
        python -m pip install --no-cache-dir -r requirements-runtime.txt -i "$PIP_INDEX_URL"; \
    else \
        python -m pip install --no-cache-dir -r requirements-runtime.txt; \
    fi

FROM build AS build-dev

ARG PIP_INDEX_URL=""

COPY app/requirements.txt /backend/requirements.txt
COPY app/requirements-dev.txt /backend/requirements-dev.txt

RUN set -eux; \
    if [ -n "$PIP_INDEX_URL" ]; then \
        python -m pip install --no-cache-dir -r requirements-dev.txt -i "$PIP_INDEX_URL"; \
    else \
        python -m pip install --no-cache-dir -r requirements-dev.txt; \
    fi

FROM build-dev AS dev

COPY app /backend/app

RUN mkdir -p /backend/logs /backend/app/static/uploads

EXPOSE 8000

CMD ["python", "/backend/app/main.py"]

FROM ${PYTHON_IMAGE} AS runtime-base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/backend \
    VIRTUAL_ENV=/opt/venv \
    PATH=/opt/venv/bin:$PATH

WORKDIR /backend

COPY --from=build /opt/venv /opt/venv
COPY app /backend/app

RUN mkdir -p /backend/logs /backend/app/static/uploads

FROM runtime-base AS prod

COPY alembic.ini /backend/alembic.ini
COPY alembic /backend/alembic

RUN adduser --disabled-password --gecos '' appuser \
    && chown -R appuser:appuser /backend
USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 \
    CMD ["python", "-c", "import sys, urllib.request; sys.exit(0 if urllib.request.urlopen('http://localhost:8000/health').getcode() == 200 else 1)"]

CMD ["uvicorn", "app.main:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]

FROM runtime-base AS staging

COPY alembic.ini /backend/alembic.ini
COPY alembic /backend/alembic

RUN adduser --disabled-password --gecos '' appuser \
    && chown -R appuser:appuser /backend
USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 \
    CMD ["python", "-c", "import sys, urllib.request; sys.exit(0 if urllib.request.urlopen('http://localhost:8000/health').getcode() == 200 else 1)"]

CMD ["uvicorn", "app.main:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
