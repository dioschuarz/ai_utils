"""Configurações do scraper e-SAJ."""

# URLs do portal e-SAJ
BASE_URL = "https://esaj.tjsp.jus.br"
SEARCH_URL = f"{BASE_URL}/cpopg/open.do"
SEARCH_POST_URL = f"{BASE_URL}/cpopg/search.do"
SHOW_URL = f"{BASE_URL}/cpopg/show.do"

# Configurações do Crawl4AI
# CrawlerRunConfig aceita apenas parâmetros específicos
# headless é configurado no AsyncWebCrawler, não no CrawlerRunConfig
CRAWLER_CONFIG = {
    "page_timeout": 30000,  # 30 segundos em milissegundos
}

# Configurações do browser (para AsyncWebCrawler)
BROWSER_CONFIG = {
    "headless": True,
}

# Timeouts e retries
REQUEST_TIMEOUT = 30
MAX_RETRIES = 3
RETRY_DELAY = 2  # segundos

# Seletores CSS principais
SELECTORS = {
    "numero_processo": "#numeroProcesso",
    "classe": "#classeProcesso",
    "assunto": "#assuntoProcesso",
    "foro": "#foroProcesso",
    "vara": "#varaProcesso",
    "juiz": "#juizProcesso",
    "distribuicao": "#dataHoraDistribuicaoProcesso",
    "controle": "#numeroControleProcesso",
    "area": "#areaProcesso",
    "valor_acao": "#valorAcaoProcesso",
    "tabela_partes": "#tablePartesPrincipais",
    "tabela_movimentacoes": "#tabelaUltimasMovimentacoes",
    "tabela_todas_movimentacoes": "#tabelaTodasMovimentacoes",
    "tramitacao_prioritaria": ".unj-tag",
}

