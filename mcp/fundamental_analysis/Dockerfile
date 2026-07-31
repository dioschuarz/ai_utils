FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim AS builder

WORKDIR /app

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_HTTP_TIMEOUT=300

COPY pyproject.toml uv.lock* /app/

RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --no-install-project --no-dev

COPY . /app

RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --no-dev && \
    find /app/.venv -name "*.pyc" -delete && \
    find /app/.venv -name "__pycache__" -delete

FROM python:3.12-slim

WORKDIR /app

ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/app \
    MALLOC_TRIM_THRESHOLD_=100000

COPY --from=builder /app/.venv /app/.venv
COPY --from=builder /app /app

EXPOSE 8000

CMD ["python", "main.py"]
