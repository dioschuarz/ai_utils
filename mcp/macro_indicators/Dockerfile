FROM ghcr.io/astral-sh/uv:python3.13-bookworm-slim

WORKDIR /app/mcp/macro_indicators

# Enable bytecode compilation
ENV UV_COMPILE_BYTECODE=1
ENV UV_LINK_MODE=copy
ENV UV_HTTP_TIMEOUT=300
ENV UV_CONCURRENT_DOWNLOADS=4

# Copy all files of macro_indicators to /app/mcp/macro_indicators
COPY . /app/mcp/macro_indicators

# Install dependencies globally in system python
RUN --mount=type=cache,target=/root/.cache/uv \
    uv pip install --system .

ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app/mcp/macro_indicators

CMD ["python", "main.py"]
