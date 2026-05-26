FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim

# Install minimal system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends     ca-certificates     && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Enable bytecode compilation
ENV UV_COMPILE_BYTECODE=1

# Copy all project files first (needed for package build)
ADD . /app

# Install dependencies
RUN --mount=type=cache,target=/root/.cache/uv     uv sync --frozen --no-dev

# Final environment setup
ENV PATH="/app/.venv/bin:\$PATH"
ENV PYTHONUNBUFFERED=1

EXPOSE 8000

CMD ["python", "-m", "src.server"]
