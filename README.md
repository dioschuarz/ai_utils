# AI Utils

Coleção de ferramentas e servidores MCP (Model Context Protocol) para análise financeira e desenvolvimento de IA.

## 📋 Índice

- [MCP Servers](#mcp-servers)
  - [Visão Geral](#visão-geral)
  - [Início Rápido](#início-rápido)
  - [Gerenciamento](#gerenciamento)
  - [Conectando de Aplicações](#conectando-de-aplicações)
- [Tools](#tools)
  - [e-SAJ Scraper](#e-saj-scraper)

---

## MCP Servers

### Visão Geral

Este projeto contém servidores MCP (Model Context Protocol) construídos com **FastMCP** que fornecem ferramentas especializadas para análise financeira:

- **Damodaran Valuation** - Ferramentas de valuation baseadas em dados do Prof. Aswath Damodaran
- **Fundamentus B3** - Dados fundamentais de ações da B3 (Brasil)

Ambos os servidores usam **FastMCP com SSE (Server-Sent Events)**, tornando-os acessíveis via HTTP de suas aplicações.

### Servidores Disponíveis

| Servidor | Endpoint | Porta | Descrição |
|----------|----------|-------|-----------|
| **Damodaran Valuation** | `http://localhost:8100/sse` | 8100 | Métricas de setores, betas, prêmios de risco por país, ratings sintéticos |
| **Fundamentus B3** | `http://localhost:8101/sse` | 8101 | Dados fundamentais de ações da B3 com cache PostgreSQL |

### Início Rápido

Os servidores rodam em **modo daemon (background)** - você **NÃO precisa manter um terminal aberto**.

#### Opção 1: Script Python (Recomendado)

```bash
# Iniciar todos os servidores em background
python3 mcp/manage_mcp_servers.py start --unified

# Verificar status
python3 mcp/manage_mcp_servers.py status
```

#### Opção 2: Script Shell

```bash
# Iniciar
./mcp/start_servers.sh

# Parar
./mcp/stop_servers.sh
```

#### Opção 3: Docker Compose Direto

```bash
cd mcp
docker compose -f docker-compose.yml up -d
```

Os servidores reiniciam automaticamente se crasharem (`restart: unless-stopped`).

### Gerenciamento

O script `mcp/manage_mcp_servers.py` fornece uma interface CLI completa:

```bash
# Listar servidores disponíveis
python3 mcp/manage_mcp_servers.py list

# Iniciar todos os servidores (modo unificado)
python3 mcp/manage_mcp_servers.py start --unified

# Iniciar servidor específico
python3 mcp/manage_mcp_servers.py start damodaran_valuation

# Iniciar com rebuild
python3 mcp/manage_mcp_servers.py start --unified --build

# Parar todos os servidores
python3 mcp/manage_mcp_servers.py stop --unified

# Ver status
python3 mcp/manage_mcp_servers.py status

# Ver logs
python3 mcp/manage_mcp_servers.py logs damodaran_valuation --follow
```

### Conectando de Aplicações

#### Python Client

```python
import asyncio
from mcp import ClientSession
from mcp.client.sse import sse_client

async def use_mcp_server():
    url = "http://localhost:8100/sse"  # Damodaran server
    
    async with sse_client(url=url) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            
            # Listar ferramentas disponíveis
            tools = await session.list_tools()
            print(f"Ferramentas: {[t.name for t in tools.tools]}")
            
            # Chamar uma ferramenta
            result = await session.call_tool(
                "get_sector_metrics",
                arguments={"sector_name": "Technology"}
            )
            print(f"Resultado: {result.content}")

asyncio.run(use_mcp_server())
```

#### Usando o Wrapper MCPClient

Para maior conveniência, use a classe `MCPClient` de `mcp/client_example.py`:

```python
from mcp.client_example import MCPClient

async def exemplo():
    async with MCPClient("http://localhost:8100/sse") as client:
        # Listar ferramentas
        tools = await client.list_tools()
        
        # Chamar ferramentas
        result = await client.call_tool(
            "get_sector_metrics",
            {"sector_name": "Technology"}
        )
        print(result)
```

#### Testando com MCP Inspector

```bash
# Servidor Damodaran
npx @modelcontextprotocol/inspector --url http://localhost:8100/sse

# Servidor Fundamentus
npx @modelcontextprotocol/inspector --url http://localhost:8101/sse
```

### Ferramentas Disponíveis

#### Damodaran Valuation

- `get_sector_metrics(sector_name)` - Retorna beta unlevered, taxa de imposto e D/E médio do setor
- `get_country_risk_premium(country)` - Retorna prêmio de risco de equity e país
- `calculate_levered_beta(sector_name, current_de_ratio)` - Aplica fórmula de Hamada
- `get_synthetic_spread(interest_coverage_ratio)` - Retorna rating e spread baseado no ICR
- `get_sector_benchmarks(sector_name)` - Retorna métricas de benchmark do setor

#### Fundamentus B3

- `get_b3_snapshot(ticker)` - Snapshot completo de uma ação B3
- `get_b3_snapshots(tickers)` - Snapshots em lote (otimizado com cache)
- `get_fundamental_metrics(ticker)` - Métricas fundamentais essenciais
- `search_tickers(query)` - Buscar ações por nome ou segmento
- `refresh_cache(ticker)` - Forçar atualização do cache
- `list_cached_tickers()` - Listar tickers em cache

### Configuração de Rede

Os servidores MCP estão configurados para:
- Escutar em `0.0.0.0` (todas as interfaces) dentro dos containers
- Expor portas no `localhost`:
  - Damodaran: `8100:8000` (host:container)
  - Fundamentus: `8101:8000` (host:container)
- Usar a rede Docker compartilhada `investment-net` para comunicação entre containers

**Acessando de outras aplicações:**
- **Mesma máquina**: Use `http://localhost:8100/sse` ou `http://localhost:8101/sse`
- **Rede Docker**: Use `http://damodaran-mcp:8000/sse` ou `http://fundamentus-mcp:8000/sse`
- **Máquina remota**: Certifique-se de que as portas estão expostas e use o IP do host

### Inicialização Automática no Boot (Opcional)

Para iniciar automaticamente quando o sistema ligar:

1. Edite o arquivo de serviço systemd:
   ```bash
   nano mcp/mcp-servers.service
   # Ajuste os caminhos se necessário
   ```

2. Instale o serviço:
   ```bash
   sudo cp mcp/mcp-servers.service /etc/systemd/system/
   sudo systemctl daemon-reload
   sudo systemctl enable mcp-servers.service
   sudo systemctl start mcp-servers.service
   ```

3. Verifique o status:
   ```bash
   sudo systemctl status mcp-servers.service
   ```

### Requisitos

- Docker e Docker Compose instalados
- Python 3.10+ (o script de gerenciamento usa apenas biblioteca padrão)

### Documentação Adicional

- **README individual do Damodaran**: `mcp/damodaran_valuation/README.md`
- **README individual do Fundamentus**: `mcp/fundamentus_b3/README.md`
- **Exemplo de cliente**: `mcp/client_example.py`

---

## Tools

### e-SAJ Scraper

Scraper para extrair dados de processos do portal e-SAJ do Tribunal de Justiça de São Paulo (TJSP) usando Crawl4AI.

#### Características

- Extração completa de dados de processos judiciais
- Suporte para conteúdo JavaScript dinâmico (via Crawl4AI)
- Validação de dados com Pydantic
- Retorno em JSON estruturado
- Preparado para futura conversão em servidor MCP

#### Instalação

Este projeto usa `uv` para gerenciamento de pacotes Python.

**Pré-requisitos:**
- Python 3.10 ou superior
- [uv](https://github.com/astral-sh/uv) instalado

**Instalação das dependências:**
```bash
cd tools
uv sync

# Instalar navegadores do Playwright (requerido pelo Crawl4AI)
playwright install chromium
playwright install-deps chromium
```

#### Uso

**Via CLI:**
```bash
# Processo único
python -m esaj_scraper 1002589-56.2018.8.26.0053

# Múltiplos processos
python main.py 1002589-56.2018.8.26.0053 1061517-43.2024.8.26.0100
```

**Via Python:**
```python
import asyncio
from esaj_scraper import EsajScraper

async def main():
    scraper = EsajScraper()
    processo = await scraper.scrape("1002589-56.2018.8.26.0053")
    print(processo.to_json_dict())

asyncio.run(main())
```

#### Testes

```bash
cd tools
python tests/test_scraper.py
```

#### Estrutura de Dados

O scraper retorna um objeto `ProcessoCompleto` com:
- Informações principais (número, classe, assunto, foro, vara, juiz, etc.)
- Partes (requerente/requerido, advogados)
- Movimentações (data, tipo, descrição, links)
- Petições
- Incidentes/Apensos
- Metadata (data de extração, status, erros)

Para mais detalhes, veja a documentação completa em `tools/README.md`.

---

## Estrutura do Projeto

```
ai_utils/
├── mcp/                          # Servidores MCP
│   ├── docker-compose.yml        # Compose unificado para todos os servidores
│   ├── manage_mcp_servers.py     # Script de gerenciamento
│   ├── client_example.py        # Exemplo de cliente Python
│   ├── start_servers.sh          # Script de inicialização
│   ├── stop_servers.sh           # Script de parada
│   ├── mcp-servers.service       # Serviço systemd (opcional)
│   ├── damodaran_valuation/      # Servidor Damodaran
│   │   ├── docker-compose.yml
│   │   ├── Dockerfile
│   │   ├── README.md
│   │   └── src/
│   └── fundamentus_b3/            # Servidor Fundamentus
│       ├── docker-compose.yml
│       ├── Dockerfile
│       ├── README.md
│       └── src/
├── tools/                         # Ferramentas diversas
│   ├── esaj_scraper/             # Scraper e-SAJ
│   └── tests/
└── README.md                      # Este arquivo
```

---

## Licença

Este projeto é para uso interno/educacional. Certifique-se de respeitar os termos de uso dos serviços externos utilizados.
