FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim

WORKDIR /app

# Install git for pandas_ta
RUN apt-get update && apt-get install -y git && rm -rf /var/lib/apt/lists/*

ENV UV_COMPILE_BYTECODE=1
ENV UV_HTTP_TIMEOUT=600
ENV UV_CONCURRENT_DOWNLOADS=4

# Copy project files
COPY pyproject.toml uv.lock README.md /app/
COPY src /app/src

# Install dependencies using pip install --system (uses pre-built wheels from PyPI)
# This avoids local compilation of numba/llvmlite
RUN --mount=type=cache,target=/root/.cache/uv \
    uv pip install --system -r pyproject.toml

ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app/src

CMD ["python", "-m", "src.server"]
