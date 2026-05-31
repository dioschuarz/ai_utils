FROM ghcr.io/astral-sh/uv:python3.13-bookworm-slim

WORKDIR /app/mcp/fundamental_analysis

# Enable bytecode compilation
ENV UV_COMPILE_BYTECODE=1
ENV UV_LINK_MODE=copy
ENV UV_HTTP_TIMEOUT=300
ENV UV_CONCURRENT_DOWNLOADS=4

# Copy all files of fundamental_analysis to /app/mcp/fundamental_analysis
COPY . /app/mcp/fundamental_analysis

# Install dependencies globally in system python
RUN --mount=type=cache,target=/root/.cache/uv \
    uv pip install --system .

ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app/mcp/fundamental_analysis

CMD ["python", "main.py"]
