"""
Unified Monolithic Financial MCP Server
Combines all 9 MCP toolsets into a single master FastMCP server endpoint.
"""

import sys
import os
from pathlib import Path
from fastmcp import FastMCP

mcp_base = Path(__file__).parent.resolve()

# Add all subdirectories to Python path
for sub in ["damodaran_valuation", "fundamental_analysis", "fundamentus_b3", "macro_indicators", "news_discovery", "technical_analysis", "web_extraction", "web_summarizer", "yfinance_mcp"]:
    src_dir = str(mcp_base / sub / "src")
    root_dir = str(mcp_base / sub)
    if os.path.exists(src_dir) and src_dir not in sys.path:
        sys.path.insert(0, src_dir)
    if os.path.exists(root_dir) and root_dir not in sys.path:
        sys.path.insert(0, root_dir)

master_mcp = FastMCP("Unified-Financial-MCP-Monolith")

# Helper to merge FastMCP tools from sub-servers
def merge_mcp_tools(sub_mcp: FastMCP):
    if hasattr(sub_mcp, "_tool_manager") and hasattr(sub_mcp._tool_manager, "_tools"):
        for name, tool in sub_mcp._tool_manager._tools.items():
            master_mcp._tool_manager._tools[name] = tool
            print(f"   + Merged tool: {name}")

print("Initializing Monolithic MCP Tool Merger...")

# 1. Damodaran
try:
    from damodaran_valuation.src.server import mcp as srv
    merge_mcp_tools(srv)
except Exception as e:
    print(f"Warning: Failed damodaran_valuation: {e}")

# 2. Fundamentus B3
try:
    from fundamentus_b3.src.server import mcp as srv
    merge_mcp_tools(srv)
except Exception as e:
    print(f"Warning: Failed fundamentus_b3: {e}")

# 3. YFinance
try:
    from yfinance_mcp.src.server import mcp as srv
    merge_mcp_tools(srv)
except Exception as e:
    print(f"Warning: Failed yfinance_mcp: {e}")

# 4. Web Summarizer
try:
    from web_summarizer.src.server import mcp as srv
    merge_mcp_tools(srv)
except Exception as e:
    print(f"Warning: Failed web_summarizer: {e}")

# 5. Technical Analyst
try:
    from technical_analysis.src.server import mcp as srv
    merge_mcp_tools(srv)
except Exception as e:
    print(f"Warning: Failed technical_analysis: {e}")

# 6. News Discovery
try:
    from news_discovery.src.server import mcp as srv
    merge_mcp_tools(srv)
except Exception as e:
    print(f"Warning: Failed news_discovery: {e}")

# 7. Web Extraction
try:
    from web_extraction.src.server import mcp as srv
    merge_mcp_tools(srv)
except Exception as e:
    print(f"Warning: Failed web_extraction: {e}")

# 8. Fundamental Analysis
try:
    from fundamental_analysis.main import mcp as srv
    merge_mcp_tools(srv)
except Exception as e:
    print(f"Warning: Failed fundamental_analysis: {e}")

# 9. Macro Indicators
try:
    from macro_indicators.main import mcp as srv
    merge_mcp_tools(srv)
except Exception as e:
    print(f"Warning: Failed macro_indicators: {e}")

app = master_mcp.http_app()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
