#!/usr/bin/env python3
"""Script de teste para o servidor MCP Fundamentus B3 via linha de comando."""

import json
import sys
from typing import Any, Dict

try:
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client
except ImportError:
    print("Erro: Biblioteca MCP não encontrada. Instale com: uv add mcp")
    sys.exit(1)

# Para testar diretamente as funções (sem MCP client)
import sys
from pathlib import Path

# Add src to path for direct imports
src_path = Path(__file__).parent / "src"
if src_path.exists():
    sys.path.insert(0, str(src_path))

try:
    from server import (
        get_b3_snapshot,
        get_b3_snapshots,
        get_fundamental_metrics,
        search_tickers,
        refresh_cache,
        list_cached_tickers,
    )
    DIRECT_TEST = True
except ImportError:
    DIRECT_TEST = False
    print("Aviso: Não foi possível importar funções diretamente. Usando cliente MCP.")


def test_direct_functions():
    """Testa as funções diretamente (sem cliente MCP)."""
    print("=" * 80)
    print("TESTE DIRETO DAS FUNÇÕES DO SERVIDOR")
    print("=" * 80)
    
    tests = [
        ("list_cached_tickers", lambda: list_cached_tickers()),
        ("search_tickers('PETR')", lambda: search_tickers("PETR")),
        ("get_b3_snapshot('PETR4')", lambda: get_b3_snapshot("PETR4")),
        ("get_fundamental_metrics('PETR4')", lambda: get_fundamental_metrics("PETR4")),
    ]
    
    for test_name, test_func in tests:
        print(f"\n[TESTE] {test_name}")
        print("-" * 80)
        try:
            result = test_func()
            print(json.dumps(result, indent=2, ensure_ascii=False, default=str))
            print("✓ Sucesso")
        except Exception as e:
            print(f"✗ Erro: {e}")
            import traceback
            traceback.print_exc()


async def test_via_mcp_client():
    """Testa via cliente MCP (requer servidor rodando)."""
    print("=" * 80)
    print("TESTE VIA CLIENTE MCP (SSE)")
    print("=" * 80)
    
    # FastMCP com SSE expõe endpoints HTTP
    # Vamos tentar usar o inspector ou fazer requisições HTTP diretas
    print("\nPara testar via cliente MCP, use:")
    print("  npx @modelcontextprotocol/inspector --url http://localhost:8101/sse")
    print("\nOu teste as ferramentas diretamente importando as funções.")


def main():
    """Função principal."""
    if DIRECT_TEST:
        test_direct_functions()
    else:
        print("Testando via cliente MCP...")
        import asyncio
        asyncio.run(test_via_mcp_client())
    
    print("\n" + "=" * 80)
    print("TESTE CONCLUÍDO")
    print("=" * 80)


if __name__ == "__main__":
    main()


