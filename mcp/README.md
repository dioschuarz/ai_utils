# MCP Servers

Servidores MCP (Model Context Protocol) para análise financeira.

## Início Rápido

```bash
# Iniciar todos os servidores
python3 manage_mcp_servers.py start --unified

# Ver status
python3 manage_mcp_servers.py status
```

## Documentação Completa

Para documentação completa, exemplos de uso, e detalhes sobre cada servidor, consulte:

- **README principal do projeto**: `/README.md` (raiz do projeto)
- **Damodaran Valuation**: `damodaran_valuation/README.md`
- **Fundamentus B3**: `fundamentus_b3/README.md`
- **Exemplo de cliente**: `client_example.py`

## Comandos Úteis

```bash
# Listar servidores
python3 manage_mcp_servers.py list

# Iniciar/parar
python3 manage_mcp_servers.py start --unified
python3 manage_mcp_servers.py stop --unified

# Logs
python3 manage_mcp_servers.py logs <servidor> --follow
```

## Endpoints

- **Damodaran**: `http://localhost:8100/sse`
- **Fundamentus**: `http://localhost:8101/sse`
