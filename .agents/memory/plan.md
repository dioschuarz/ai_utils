# Technical Plan: TD-20: Upgrade MCP Infrastructure to FastMCP v3 (HTTP)

## 🎯 Proposed Changes

### Component: Dependencies
- [MODIFY] `mcp/damodaran_valuation/pyproject.toml` (file:///home/ds/projects/ai_utils/mcp/damodaran_valuation/pyproject.toml): Update to `fastmcp>=0.3.0`.
- [MODIFY] `mcp/fundamentus_b3/pyproject.toml` (file:///home/ds/projects/ai_utils/mcp/fundamentus_b3/pyproject.toml): Update to `fastmcp>=0.3.0`.
- [MODIFY] `mcp/technical_analyst/pyproject.toml` (file:///home/ds/projects/ai_utils/mcp/technical_analyst/pyproject.toml): Update to `fastmcp>=0.3.0`.
- [MODIFY] `mcp/web_summarizer_mcp/pyproject.toml` (file:///home/ds/projects/ai_utils/mcp/web_summarizer_mcp/pyproject.toml): Update to `fastmcp>=0.3.0`.
- [MODIFY] `mcp/yfinance_mcp/pyproject.toml` (file:///home/ds/projects/ai_utils/mcp/yfinance_mcp/pyproject.toml): Update to `fastmcp>=0.3.0`.

### Component: Servers (Transport Update)
- [MODIFY] `mcp/damodaran_valuation/src/server.py` (file:///home/ds/projects/ai_utils/mcp/damodaran_valuation/src/server.py): Change `mcp.run(transport="sse")` to `mcp.run(transport="http")`.
- [MODIFY] `mcp/fundamentus_b3/src/server.py` (file:///home/ds/projects/ai_utils/mcp/fundamentus_b3/src/server.py): Change `mcp.run(transport="sse")` to `mcp.run(transport="http")`.
- [MODIFY] `mcp/technical_analyst/src/server.py` (file:///home/ds/projects/ai_utils/mcp/technical_analyst/src/server.py): Change `mcp.run(transport="sse")` to `mcp.run(transport="http")`.
- [MODIFY] `mcp/web_summarizer_mcp/src/server.py` (file:///home/ds/projects/ai_utils/mcp/web_summarizer_mcp/src/server.py): Change `mcp.run(transport="sse")` to `mcp.run(transport="http")`.
- [MODIFY] `mcp/yfinance_mcp/src/server.py` (file:///home/ds/projects/ai_utils/mcp/yfinance_mcp/src/server.py): Change `mcp.run(transport="sse")` to `mcp.run(transport="http")`.

### Component: Client Wrappers
- [MODIFY] `mcp/client_example.py` (file:///home/ds/projects/ai_utils/mcp/client_example.py): Refactor `MCPClient` and standalone functions to use FastMCP v3 HTTP client primitives.
- [MODIFY] `mcp/benchmark_news_summarized_comparison.py` (file:///home/ds/projects/ai_utils/mcp/benchmark_news_summarized_comparison.py): Update internal `MCPClient` to match new HTTP transport.

### Component: Infrastructure & Config
- [MODIFY] `mcp/docker-compose.yml` (file:///home/ds/projects/ai_utils/mcp/docker-compose.yml): Update healthchecks (URL paths from `/sse` to `/`).
- [MODIFY] `mcp/manage_mcp_servers.py` (file:///home/ds/projects/ai_utils/mcp/manage_mcp_servers.py): Update default URLs.

### Component: Tests
- [MODIFY] `tests/mcp/web_summarizer/test_web_summarizer_flow.py` (file:///home/ds/projects/ai_utils/tests/mcp/web_summarizer/test_web_summarizer_flow.py): Update `MCPClient` mock/wrapper.

## 💥 Blast Radius Analysis
- **MCP Clients**: All clients relying on `sse_client` or `ClientSession` (SSE) will break until updated.
- **Docker Orchestration**: Healthchecks will fail until URLs are updated.
- **Listing Methods**: FastMCP v3 returns `List` for tools/resources instead of `Dict`. Downstream logic needs verification.
- **Auth**: New HTTP transport requires explicit auth header handling which might differ from SSE.

## ✅ Verification Plan
- **Automated Tests**:
  - `pytest tests/mcp/test_servers.py --no-cov`
  - `pytest tests/mcp/technical_analyst/test_technical_analysis.py --no-cov`
  - `pytest tests/mcp/web_summarizer/test_web_summarizer_flow.py --no-cov`
- **Manual Verification**:
  - Run `python mcp/client_example.py` to verify connection to updated servers.
  - Run `python mcp/benchmark_news_summarized_comparison.py PETR4.SA 2` to verify full flow.
  - Check Docker logs: `docker compose -f mcp/docker-compose.yml logs -f`.
