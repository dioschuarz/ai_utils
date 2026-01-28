FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim

WORKDIR /app

ENV UV_COMPILE_BYTECODE=1
ENV UV_HTTP_TIMEOUT=300
ENV UV_CONCURRENT_DOWNLOADS=4

COPY pyproject.toml README.md /app/
COPY src /app/src

RUN --mount=type=cache,target=/root/.cache/uv \
    uv pip install --system -r pyproject.toml

ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app/src

CMD ["python", "-m", "src.server"]
