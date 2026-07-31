# Multi-stage ultra-optimized Dockerfile for yfinance-mcp

# --- Stage 1: Build virtualenv with UV ---
FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim AS builder

WORKDIR /app

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_HTTP_TIMEOUT=300

COPY pyproject.toml uv.lock /app/

RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-install-project --no-dev

COPY . /app

RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev && \
    find /app/.venv -name "*.pyc" -delete && \
    find /app/.venv -name "__pycache__" -delete

# --- Stage 2: Ultra-slim Runtime Image ---
FROM python:3.12-slim

WORKDIR /app

# Memory & Runtime Optimizations
ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/app/src \
    MALLOC_TRIM_THRESHOLD_=100000 \
    MPLCONFIGDIR=/tmp/matplotlib

# Copy virtual environment and source code
COPY --from=builder /app/.venv /app/.venv
COPY --from=builder /app/src /app/src

EXPOSE 8000

CMD ["python", "-m", "src.server"]
