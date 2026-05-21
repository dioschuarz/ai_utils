# Tasks: TD-20: Upgrade MCP Infrastructure to FastMCP v3 (HTTP)

## 🛠 Preparation
- [x] Update `pyproject.toml` in all `mcp/` subprojects to include `fastmcp>=0.3.0`. [x]
- [x] Run `uv sync` in subprojects to update lockfiles. [x]

## 🚀 Server Implementation
- [x] Update `mcp/damodaran_valuation/src/server.py` to `transport="http"` and correct imports. [x]
- [x] Update `mcp/fundamentus_b3/src/server.py` to `transport="http"` and correct imports. [x]
- [x] Update `mcp/technical_analyst/src/server.py` to `transport="http"` and correct imports. [x]
- [x] Update `mcp/web_summarizer_mcp/src/server.py` to `transport="http"` and correct imports. [x]
- [x] Update `mcp/yfinance_mcp/src/server.py` to `transport="http"` and correct imports. [x]

## 🔗 Client Refactoring
- [x] Refactor `mcp/client_example.py` `MCPClient` for HTTP (using `fastmcp.client.Client`). [x]
- [x] Update standalone functions in `mcp/client_example.py`. [x]
- [x] Update `mcp/benchmark_news_summarized_comparison.py` `MCPClient`. [x]

## 🌐 Infrastructure & Tests
- [x] Update healthcheck URLs in `mcp/docker-compose.yml` to use `/mcp`. [x]
- [x] Update default URLs in `mcp/manage_mcp_servers.py` to use `/mcp`. [x]
- [x] Update `tests/mcp/web_summarizer/test_web_summarizer_flow.py` to use `/mcp` and correct `CallToolResult` handling. [x]

## ✅ Verification
- [x] Run server connection tests: `pytest tests/mcp/test_servers.py`. [x]
- [x] Run web summarizer flow tests: `pytest tests/mcp/web_summarizer/test_web_summarizer_flow.py`. [x]
- [x] Verify manually with `mcp/client_example.py`. [x]
