"""Scraper principal usando Crawl4AI para extrair dados do portal e-SAJ."""

import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional, Tuple
from crawl4ai import AsyncWebCrawler, CrawlerRunConfig
from playwright.async_api import async_playwright
from .models import ProcessoCompleto, InformacoesPrincipais, Parte, Movimentacao, Peticao, Incidente, Metadata
from .parser import (
    parse_process_header,
    parse_partes,
    parse_movimentacoes,
    parse_peticoes,
    parse_incidentes,
)
from .config import SEARCH_URL, SEARCH_POST_URL, SHOW_URL, CRAWLER_CONFIG, BASE_URL, BROWSER_CONFIG


class EsajScraper:
    """Scraper para extrair dados de processos do portal e-SAJ do TJSP."""
    
    def __init__(self):
        """Inicializa o scraper."""
        self.crawler_config = CrawlerRunConfig(**CRAWLER_CONFIG)
        self.browser_config = BROWSER_CONFIG
    
    def _normalize_process_number(self, numero: str) -> Tuple[str, str]:
        """
        Normaliza o número do processo para o formato esperado pelo portal.
        Retorna (numero_formatado, foro).
        """
        # Remove espaços e pontos extras
        numero = numero.strip().replace(' ', '')
        
        # Formato esperado: NNNNNNN-DD.AAAA.J.TR.OOOO
        # Exemplo: 1002589-56.2018.8.26.0053
        
        # Se já está no formato correto, extrai o foro (últimos 4 dígitos)
        match = re.match(r'(\d{7}-\d{2}\.\d{4}\.\d\.\d{2}\.)(\d{4})', numero)
        if match:
            numero_base = match.group(1)
            foro = match.group(2)
            return numero, foro
        
        # Tenta parsear formato alternativo
        parts = numero.split('.')
        if len(parts) >= 5:
            foro = parts[-1]
            return numero, foro
        
        return numero, ""
    
    async def _search_process(self, numero_processo: str) -> Optional[str]:
        """
        Realiza busca do processo no portal preenchendo o formulário corretamente
        e aguarda o redirecionamento para a página de detalhes.
        """
        from bs4 import BeautifulSoup
        
        numero_formatado, foro_cod = self._normalize_process_number(numero_processo)
        
        # Extrair componentes do número do processo para preencher os campos corretos
        # Formato: NNNNNNN-DD.AAAA.J.TR.OOOO
        # Exemplo: 1002589-56.2018.8.26.0053
        match = re.match(r'(\d{7})-(\d{2})\.(\d{4})\.(\d)\.(\d{2})\.(\d{4})', numero_formatado)
        if not match:
            return None
            
        numero_seq = match.group(1)  # 1002589
        digito = match.group(2)      # 56
        ano = match.group(3)         # 2018
        segmento = match.group(4)    # 8
        tribunal = match.group(5)    # 26
        foro_cod = match.group(6)    # 0053
        
        # Quebrar o número em duas partes conforme validação do site:
        # Parte 1: NNNNNNN-DD.AAAA (o sistema preenche automaticamente o J.TR = 8.26)
        # Parte 2: OOOO (código do foro - últimos 4 dígitos)
        parte1 = f"{numero_seq}-{digito}.{ano}"  # 1002589-56.2018 (sistema adiciona .8.26 automaticamente)
        parte2 = foro_cod  # 0053
        
        # Usar Playwright diretamente para interagir com o formulário
        # Isso garante que mantemos a mesma sessão durante todo o processo
        async with async_playwright() as p:
            try:
                # Iniciar navegador
                browser = await p.chromium.launch(
                    headless=self.browser_config.get('headless', True)
                )
                context = await browser.new_context()
                page = await context.new_page()
                
                # Navegar até a página de busca
                await page.goto(SEARCH_URL, wait_until='networkidle')
                
                # Selecionar "Número do Processo" no dropdown se necessário
                cb_pesquisa = page.locator('select[name="cbPesquisa"]')
                if await cb_pesquisa.count() > 0:
                    await cb_pesquisa.select_option('NUMPROC')
                    await page.wait_for_timeout(500)
                
                # Preencher número do processo em duas partes conforme validação do site
                # Parte 1: NNNNNNN-DD.AAAA (sistema preenche automaticamente o J.TR = 8.26)
                numero_input = page.locator('#numeroDigitoAnoUnificado')
                await numero_input.wait_for(state='visible', timeout=5000)
                
                # Preencher primeira parte
                await numero_input.fill(parte1)
                
                # Disparar evento blur/Tab para que o JavaScript valide a primeira parte
                await numero_input.blur()
                
                # Aguardar que o sistema preencha automaticamente o campo J.TR (8.26)
                try:
                    await page.wait_for_function(
                        "document.querySelector('#JTRNumeroUnificado')?.value !== ''",
                        timeout=3000
                    )
                except:
                    await page.wait_for_timeout(1000)
                
                # Parte 2: Preencher o código do foro (0053)
                foro_input = page.locator('#foroNumeroUnificado')
                await foro_input.wait_for(state='visible', timeout=5000)
                
                # Preencher segunda parte (código do foro)
                await foro_input.fill(parte2)
                
                # Disparar evento blur para que o JavaScript processe o foro
                await foro_input.blur()
                await page.wait_for_timeout(1000)  # Aguardar validação JavaScript do foro
                
                print(f"[DEBUG] Parte 1: '{parte1}', Parte 2 (foro): '{parte2}'", file=sys.stderr)
                
                # Clicar no botão de busca
                submit_btn = page.locator('#botaoConsultarProcessos')
                await submit_btn.click()
                
                # Aguardar navegação para show.do
                # O portal redireciona para show.do após a busca bem-sucedida
                try:
                    # Esperar até que a URL contenha 'show.do' ou apareça o elemento #numeroProcesso
                    await page.wait_for_function(
                        "window.location.href.includes('show.do') || document.querySelector('#numeroProcesso')",
                        timeout=15000
                    )
                    # Aguardar mais um pouco para garantir que a página carregou completamente
                    await page.wait_for_load_state('networkidle', timeout=10000)
                except Exception as e:
                    print(f"[DEBUG] Erro ao aguardar navegação: {e}", file=sys.stderr)
                    # Aguardar um pouco mesmo em caso de erro
                    await page.wait_for_timeout(2000)
                
                # Obter URL atual
                current_url = page.url
                print(f"[DEBUG] URL após clique: {current_url}", file=sys.stderr)
                
                # Obter HTML da página
                html = await page.content()
                
                # Debug: salvar HTML dentro do diretório esaj_scraper
                debug_dir = Path(__file__).parent / "debug"
                debug_dir.mkdir(exist_ok=True)
                debug_file = debug_dir / f"playwright_result_{numero_processo.replace('.', '_').replace('-', '_')}.html"
                with open(debug_file, "w", encoding="utf-8") as f:
                    f.write(html)
                print(f"[DEBUG] HTML salvo em: {debug_file}", file=sys.stderr)
                
                await browser.close()
                
                # Verificar se estamos na página de detalhes
                soup = BeautifulSoup(html, 'lxml')
                numero_processo_element = soup.find(id="numeroProcesso")
                print(f"[DEBUG] Elemento #numeroProcesso encontrado: {numero_processo_element is not None}", file=sys.stderr)
                
                if numero_processo_element or 'show.do' in current_url:
                    print(f"[DEBUG] Retornando URL: {current_url}", file=sys.stderr)
                    return current_url
                
                # Se não, procurar por links na página
                links = soup.find_all('a', href=re.compile(r'show\.do'))
                print(f"[DEBUG] Links encontrados: {len(links)}", file=sys.stderr)
                
                if links:
                    href = links[0].get('href')
                    print(f"[DEBUG] Primeiro link: {href}", file=sys.stderr)
                    if href:
                        if href.startswith('http'):
                            return href
                        else:
                            full_url = f"{BASE_URL}{href}" if href.startswith('/') else f"{BASE_URL}/{href}"
                            print(f"[DEBUG] Retornando URL completa: {full_url}", file=sys.stderr)
                            return full_url
                
                print(f"[DEBUG] Nenhuma URL encontrada, retornando None", file=sys.stderr)
                return None
                
            except Exception as e:
                print(f"Erro ao buscar processo: {e}", file=sys.stderr)
                import traceback
                traceback.print_exc()
                try:
                    await browser.close()
                except:
                    pass
                return None
    
    async def _get_process_details(self, url: str) -> Optional[str]:
        """
        Obtém o HTML da página de detalhes do processo.
        """
        async with AsyncWebCrawler(**self.browser_config) as crawler:
            try:
                result = await crawler.arun(url=url, config=self.crawler_config)
                
                if result.success and result.html:
                    return result.html
                
                return None
                
            except Exception as e:
                print(f"Erro ao obter detalhes do processo: {e}")
                return None
    
    async def scrape(self, numero_processo: str) -> ProcessoCompleto:
        """
        Extrai dados completos de um processo do portal e-SAJ.
        
        Args:
            numero_processo: Número do processo no formato NNNNNNN-DD.AAAA.J.TR.OOOO
            
        Returns:
            ProcessoCompleto: Objeto contendo todos os dados extraídos
        """
        try:
            # Passo 1: Buscar o processo e obter URL da página de detalhes
            detail_url = await self._search_process(numero_processo)
            
            if not detail_url:
                raise Exception(f"Não foi possível encontrar a página de detalhes do processo após a busca. Verifique se o número está correto: {numero_processo}")
            
            # Passo 2: Obter HTML da página de detalhes
            html = await self._get_process_details(detail_url)
            
            if not html:
                raise Exception(f"Não foi possível obter dados do processo {numero_processo}")
            
            # Debug: salvar HTML para inspeção dentro do diretório esaj_scraper
            debug_dir = Path(__file__).parent / "debug"
            debug_dir.mkdir(exist_ok=True)
            debug_file = debug_dir / f"processo_{numero_processo.replace('.', '_').replace('-', '_')}.html"
            with open(debug_file, "w", encoding="utf-8") as f:
                f.write(html)
            print(f"[DEBUG] HTML salvo em: {debug_file}", file=sys.stderr)
            
            # Passo 3: Parsear todas as seções
            informacoes_principais = parse_process_header(html)
            # Garantir que o número do processo está preenchido mesmo se não encontrado no HTML
            if not informacoes_principais.numero_processo:
                informacoes_principais.numero_processo = numero_processo
            partes = parse_partes(html)
            movimentacoes = parse_movimentacoes(html)
            peticoes = parse_peticoes(html)
            incidentes = parse_incidentes(html)
            
            # Passo 4: Criar objeto completo com metadata
            metadata = Metadata(
                data_extracao=datetime.now(),
                status="success"
            )
            
            processo = ProcessoCompleto(
                informacoes_principais=informacoes_principais,
                partes=partes,
                movimentacoes=movimentacoes,
                peticoes=peticoes,
                incidentes=incidentes,
                metadata=metadata
            )
            
            return processo
            
        except Exception as e:
            # Retornar objeto com erro
            metadata = Metadata(
                data_extracao=datetime.now(),
                status="error",
                erro=str(e)
            )
            
            # Criar informações principais mínimas
            informacoes_principais = InformacoesPrincipais(numero_processo=numero_processo)
            
            return ProcessoCompleto(
                informacoes_principais=informacoes_principais,
                metadata=metadata
            )
    
    async def scrape_multiple(self, numeros_processos: list[str]) -> list[ProcessoCompleto]:
        """
        Extrai dados de múltiplos processos.
        
        Args:
            numeros_processos: Lista de números de processos
            
        Returns:
            Lista de ProcessoCompleto
        """
        import asyncio
        
        tasks = [self.scrape(numero) for numero in numeros_processos]
        resultados = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Converter exceções em objetos de erro
        processos = []
        for i, resultado in enumerate(resultados):
            if isinstance(resultado, Exception):
                metadata = Metadata(
                    data_extracao=datetime.now(),
                    status="error",
                    erro=str(resultado)
                )
                informacoes_principais = InformacoesPrincipais(numero_processo=numeros_processos[i])
                processos.append(ProcessoCompleto(
                    informacoes_principais=informacoes_principais,
                    metadata=metadata
                ))
            else:
                processos.append(resultado)
        
        return processos

