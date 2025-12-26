# e-SAJ Portal Scraper

Scraper para extrair dados de processos do portal e-SAJ do Tribunal de Justiça de São Paulo (TJSP) usando Crawl4AI.

## Características

- Extração completa de dados de processos judiciais
- Suporte para conteúdo JavaScript dinâmico (via Crawl4AI)
- Validação de dados com Pydantic
- Retorno em JSON estruturado
- Preparado para futura conversão em servidor MCP

## Instalação

Este projeto usa `uv` para gerenciamento de pacotes Python.

### Pré-requisitos

- Python 3.10 ou superior
- [uv](https://github.com/astral-sh/uv) instalado

### Instalação das dependências

```bash
cd tools
uv sync

# Instalar navegadores do Playwright (requerido pelo Crawl4AI)
playwright install chromium

# Instalar dependências do sistema (pode requerer sudo)
playwright install-deps chromium
# OU manualmente (Ubuntu/Debian):
# sudo apt-get install -y libnspr4 libnss3 libatk1.0-0 libatk-bridge2.0-0 libcups2 libdrm2 libxkbcommon0 libxcomposite1 libxdamage1 libxfixes3 libxrandr2 libgbm1 libasound2 libpango-1.0-0 libcairo2
```

Ou para instalar globalmente:

```bash
cd tools
uv pip install -e .
```

## Uso

### Via CLI

#### Processo único

```bash
# Usando o módulo
python -m esaj_scraper 1002589-56.2018.8.26.0053

# Ou usando o script principal
python main.py 1002589-56.2018.8.26.0053
```

#### Múltiplos processos

```bash
python main.py 1002589-56.2018.8.26.0053 1061517-43.2024.8.26.0100 1090340-03.2019.8.26.0100
```

### Via Python

```python
import asyncio
from esaj_scraper import EsajScraper

async def main():
    scraper = EsajScraper()
    
    # Processo único
    processo = await scraper.scrape("1002589-56.2018.8.26.0053")
    print(processo.to_json_dict())
    
    # Múltiplos processos
    processos = await scraper.scrape_multiple([
        "1002589-56.2018.8.26.0053",
        "1061517-43.2024.8.26.0100",
        "1090340-03.2019.8.26.0100"
    ])
    
    for processo in processos:
        print(processo.to_json_dict())

asyncio.run(main())
```

## Testes

Os testes usam os seguintes números de processo:

1. `1002589-56.2018.8.26.0053`
2. `1061517-43.2024.8.26.0100`
3. `1090340-03.2019.8.26.0100`

### Executar testes

```bash
cd tools
python tests/test_scraper.py
```

Os testes irão:
1. Testar extração de um processo único
2. Testar extração de múltiplos processos
3. Testar cada processo individualmente
4. Salvar resultados JSON em arquivos na pasta `tests/`

## Estrutura de Dados

O scraper retorna um objeto `ProcessoCompleto` com a seguinte estrutura:

```json
{
  "informacoes_principais": {
    "numero_processo": "1002589-56.2018.8.26.0053",
    "classe": "Procedimento Comum Cível",
    "assunto": "Multas e demais Sanções",
    "foro": "Foro Central - Fazenda Pública/Acidentes",
    "vara": "10ª Vara de Fazenda Pública",
    "juiz": "Maricy Maraldi",
    "distribuicao": "23/01/2018 às 15:30 - Livre",
    "controle": "2018/000131",
    "area": "Cível",
    "valor_acao": "R$ 11.358,14",
    "tramitacao_prioritaria": false
  },
  "partes": [
    {
      "tipo_participacao": "Reqte",
      "nome": "SERVOPA ADMINISTRADORA DE CONSÓRCIO LTDA",
      "advogados": [
        {
          "nome": "Gabriel Antonio Henke Neiva de Lima Filho",
          "oab": "23378/PR"
        }
      ]
    }
  ],
  "movimentacoes": [
    {
      "data": "07/07/2025",
      "tipo": "Execução/Cumprimento de Sentença Iniciada (o)",
      "descricao": "Execução/Cumprimento de Sentença Iniciada (o)",
      "detalhes": "0018720-79.2025.8.26.0053 - Cumprimento de sentença",
      "link_documento": null
    }
  ],
  "peticoes": [
    {
      "data": "12/09/2018",
      "tipo": "Emenda à Inicial"
    }
  ],
  "incidentes": [
    {
      "data_recebimento": "03/07/2025",
      "classe": "Cumprimento de sentença",
      "numero_processo": "0018720-79.2025.8.26.0053",
      "tipo": null
    }
  ],
  "metadata": {
    "data_extracao": "2025-01-XXTXX:XX:XX",
    "status": "success",
    "erro": null
  }
}
```

## Campos Extraídos

### Informações Principais
- Número do processo
- Classe
- Assunto
- Foro
- Vara
- Juiz
- Distribuição
- Controle
- Área
- Valor da ação
- Tramitação prioritária

### Partes
- Tipo de participação (Requerente/Requerido)
- Nome da parte
- Advogados (nome e OAB)

### Movimentações
- Data
- Tipo/Movimento
- Descrição
- Detalhes
- Links para documentos (quando disponível)

### Petições
- Data
- Tipo de petição

### Incidentes/Apensos
- Data de recebimento
- Classe
- Número do processo relacionado

## Formato do Número de Processo

O scraper aceita números de processo no formato unificado:
- `NNNNNNN-DD.AAAA.J.TR.OOOO`
- Exemplo: `1002589-56.2018.8.26.0053`

Onde:
- `NNNNNNN`: Número sequencial (7 dígitos)
- `DD`: Dígito verificador (2 dígitos)
- `AAAA`: Ano (4 dígitos)
- `J`: Segmento do Poder Judiciário (1 dígito)
- `TR`: Tribunal (2 dígitos)
- `OOOO`: Foro (4 dígitos)

## Tratamento de Erros

O scraper trata os seguintes casos de erro:
- Processo não encontrado
- Timeout de requisições
- Mudanças na estrutura do HTML
- Dados incompletos
- Erros de rede

Em caso de erro, o objeto retornado terá `metadata.status = "error"` e `metadata.erro` contendo a mensagem de erro.

## Estrutura do Projeto

```
tools/
├── __init__.py
├── pyproject.toml
├── main.py
├── esaj_scraper/
│   ├── __init__.py
│   ├── scraper.py          # Classe principal do scraper
│   ├── parser.py           # Funções de parsing do HTML
│   ├── models.py           # Modelos de dados (Pydantic)
│   └── config.py           # Configurações
├── tests/
│   ├── __init__.py
│   └── test_scraper.py     # Testes com os 3 números de processo
└── README.md
```

## Dependências

- `crawl4ai>=0.3.0` - Framework para web scraping com suporte a JavaScript
- `pydantic>=2.0.0` - Validação e serialização de dados
- `beautifulsoup4>=4.12.0` - Parsing de HTML
- `lxml>=5.0.0` - Parser XML/HTML rápido
- `aiohttp>=3.9.0` - Cliente HTTP assíncrono

## Notas

- O scraper respeita os termos de uso do portal e-SAJ
- Recomenda-se usar com moderação para não sobrecarregar o servidor
- O portal pode implementar proteções contra scraping (CAPTCHA, rate limiting, etc.)
- Estrutura do HTML pode mudar, exigindo atualizações no parser

## Preparação para MCP Server

Este projeto foi estruturado para facilitar a conversão futura em um servidor MCP (Model Context Protocol). Os módulos são independentes e a interface CLI pode ser facilmente adaptada para servir como endpoints MCP.

## Licença

Este projeto é para uso interno/educacional. Certifique-se de respeitar os termos de uso do portal e-SAJ ao utilizá-lo.

