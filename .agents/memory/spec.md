# Specification: TD-20: Upgrade MCP Infrastructure to FastMCP v3 (HTTP)

## 🎯 Goal
Migrate MCP client and server communication from SSE (Server-Sent Events) to direct HTTP using FastMCP v3 to improve reliability, simplify the handshake protocol, and align with modern MCP standards.

## 📋 Requirements
- [ ] Upgrade `pyproject.toml` to `fastmcp>=0.3.0` and remove legacy MCP dependencies.
- [ ] Refactor `MCPClient` to use `StreamableHttpTransport` instead of SSE-based transport.
- [ ] Replace `MCPProtocolHandler` with a direct HTTP client implementation using FastMCP v3 primitives.
- [ ] Update JSON-RPC 2.0 request handling to remove SSE handshake logic.
- [ ] Configure explicit authentication headers via environment variables.
- [ ] Update method signatures: Refactor code relying on "listing" methods to handle List returns instead of Dictionaries.
- [ ] Verify Langfuse and OpenTelemetry context injection works with the new HTTP transport.

## 📐 Technical Boundaries
- **Runtime**: Python 3.13
- **Primary Library**: FastMCP v3
- **Transport**: HTTP (Direct)
- **Tracing**: Langfuse, OpenTelemetry

## ⚠️ Constraints & Edge Cases
- Ensure backward compatibility or clear migration path for existing MCP servers in the repo.
- Handle connection timeouts and retries in the new HTTP transport.
- Validate that all existing tools are still discoverable and callable.
