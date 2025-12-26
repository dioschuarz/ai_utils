"""Scraper principal usando Crawl4AI para extrair dados do portal e-SAJ."""

import re
import sys
import os
import json
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

# #region agent log
LOG_PATH = "/home/ds/projects/ai_utils/.cursor/debug.log"
# #endregion


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
    
    def _log_debug(self, location: str, message: str, data: dict, hypothesis_id: str = ""):
        """Helper para logging de debug."""
        # #region agent log
        try:
            log_entry = {
                "id": f"log_{int(datetime.now().timestamp() * 1000)}",
                "timestamp": int(datetime.now().timestamp() * 1000),
                "location": location,
                "message": message,
                "data": data,
                "sessionId": "debug-session",
                "runId": "run1",
                "hypothesisId": hypothesis_id
            }
            with open(LOG_PATH, "a", encoding="utf-8") as f:
                f.write(json.dumps(log_entry) + "\n")
        except Exception:
            pass
        # #endregion
    
    async def _search_process(self, numero_processo: str) -> Optional[str]:
        """
        Realiza busca do processo no portal preenchendo o formulário corretamente
        e aguarda o redirecionamento para a página de detalhes.
        """
        from bs4 import BeautifulSoup
        
        # #region agent log
        self._log_debug("scraper.py:_search_process:entry", "Iniciando busca do processo", {"numero_processo": numero_processo}, "A")
        # #endregion
        
        numero_formatado, foro_cod = self._normalize_process_number(numero_processo)
        
        # #region agent log
        self._log_debug("scraper.py:_search_process:normalize", "Número normalizado", {"numero_formatado": numero_formatado, "foro_cod": foro_cod}, "A")
        # #endregion
        
        # Extrair componentes do número do processo para preencher os campos corretos
        # Formato: NNNNNNN-DD.AAAA.J.TR.OOOO
        # Exemplo: 1002589-56.2018.8.26.0053
        match = re.match(r'(\d{7})-(\d{2})\.(\d{4})\.(\d)\.(\d{2})\.(\d{4})', numero_formatado)
        if not match:
            # #region agent log
            self._log_debug("scraper.py:_search_process:parse_error", "Falha ao parsear número do processo", {"numero_formatado": numero_formatado}, "A")
            # #endregion
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
        
        # #region agent log
        self._log_debug("scraper.py:_search_process:parsed", "Componentes do processo parseados", {"numero_seq": numero_seq, "digito": digito, "ano": ano, "segmento": segmento, "tribunal": tribunal, "foro_cod": foro_cod, "parte1": parte1, "parte2": parte2}, "A")
        # #endregion
        
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
                
                # #region agent log
                self._log_debug("scraper.py:_search_process:page_loaded", "Página de busca carregada", {"url": SEARCH_URL, "current_url": page.url}, "B")
                # #endregion
                
                # Selecionar "Número do Processo" no dropdown se necessário
                cb_pesquisa = page.locator('select[name="cbPesquisa"]')
                if await cb_pesquisa.count() > 0:
                    await cb_pesquisa.select_option('NUMPROC')
                    await page.wait_for_timeout(500)
                    # #region agent log
                    self._log_debug("scraper.py:_search_process:dropdown_selected", "Dropdown selecionado", {"option": "NUMPROC"}, "B")
                    # #endregion
                
                # Preencher número do processo em duas partes conforme validação do site
                # Parte 1: NNNNNNN-DD.AAAA (sistema preenche automaticamente o J.TR = 8.26)
                numero_input = page.locator('#numeroDigitoAnoUnificado')
                await numero_input.wait_for(state='visible', timeout=5000)
                
                # #region agent log
                input_value_before = await numero_input.input_value()
                self._log_debug("scraper.py:_search_process:before_fill_part1", "Antes de preencher parte 1", {"input_value_before": input_value_before, "parte1": parte1}, "A")
                # #endregion
                
                # Preencher primeira parte
                await numero_input.fill(parte1)
                
                # #region agent log
                input_value_after_part1 = await numero_input.input_value()
                self._log_debug("scraper.py:_search_process:after_fill_part1", "Após preencher parte 1", {"input_value_after_part1": input_value_after_part1}, "A")
                # #endregion
                
                # Disparar evento blur/Tab para que o JavaScript valide a primeira parte
                await numero_input.blur()
                
                # Aguardar que o sistema preencha automaticamente o campo J.TR (8.26)
                try:
                    await page.wait_for_function(
                        "document.querySelector('#JTRNumeroUnificado')?.value !== ''",
                        timeout=3000
                    )
                    # #region agent log
                    jtr_value = await page.locator('#JTRNumeroUnificado').input_value()
                    self._log_debug("scraper.py:_search_process:jtr_auto_filled", "Campo J.TR preenchido automaticamente", {"jtr_value": jtr_value}, "D")
                    # #endregion
                except:
                    # #region agent log
                    self._log_debug("scraper.py:_search_process:jtr_not_filled", "Campo J.TR não foi preenchido automaticamente", {}, "D")
                    # #endregion
                    await page.wait_for_timeout(1000)
                
                # #region agent log
                input_value_after_blur = await numero_input.input_value()
                self._log_debug("scraper.py:_search_process:after_blur_part1", "Após blur da parte 1", {"input_value_after_blur": input_value_after_blur}, "D")
                # #endregion
                
                # Parte 2: Preencher o código do foro (0053)
                # Tentar encontrar o campo do foro - pode ser #foroNumeroUnificado ou outro seletor
                foro_input = page.locator('#foroNumeroUnificado')
                await foro_input.wait_for(state='visible', timeout=5000)
                
                # #region agent log
                foro_value_before = await foro_input.input_value()
                self._log_debug("scraper.py:_search_process:before_fill_part2", "Antes de preencher parte 2 (foro)", {"foro_value_before": foro_value_before, "parte2": parte2}, "A")
                # #endregion
                
                # Preencher segunda parte (código do foro)
                await foro_input.fill(parte2)
                
                # #region agent log
                foro_value_after = await foro_input.input_value()
                self._log_debug("scraper.py:_search_process:after_fill_part2", "Após preencher parte 2 (foro)", {"foro_value_after": foro_value_after}, "A")
                # #endregion
                
                # Disparar evento blur para que o JavaScript processe o foro
                await foro_input.blur()
                await page.wait_for_timeout(1000)  # Aguardar validação JavaScript do foro
                
                # #region agent log
                foro_value_after_blur = await foro_input.input_value()
                hidden_value = await page.locator('#nuProcessoUnificadoFormatado').input_value() if await page.locator('#nuProcessoUnificadoFormatado').count() > 0 else ""
                self._log_debug("scraper.py:_search_process:after_blur_part2", "Após blur da parte 2", {"foro_value_after_blur": foro_value_after_blur, "hidden_value": hidden_value}, "D")
                # #endregion
                
                print(f"[DEBUG] Parte 1: '{parte1}', Parte 2 (foro): '{parte2}'", file=sys.stderr)
                print(f"[DEBUG] foroNumeroUnificado: '{foro_value_after_blur}', nuProcessoUnificadoFormatado: '{hidden_value}'", file=sys.stderr)
                
                # Clicar no botão de busca
                submit_btn = page.locator('#botaoConsultarProcessos')
                
                # #region agent log
                btn_count = await submit_btn.count()
                btn_visible = await submit_btn.is_visible() if btn_count > 0 else False
                self._log_debug("scraper.py:_search_process:before_click", "Antes de clicar no botão", {"btn_count": btn_count, "btn_visible": btn_visible, "url_before": page.url}, "B")
                # #endregion
                
                await submit_btn.click()
                
                # #region agent log
                self._log_debug("scraper.py:_search_process:after_click", "Após clicar no botão", {"url_after_click": page.url}, "B")
                # #endregion
                
                # Aguardar navegação para show.do
                # O portal redireciona para show.do após a busca bem-sucedida
                try:
                    # Esperar até que a URL contenha 'show.do' ou apareça o elemento #numeroProcesso
                    await page.wait_for_function(
                        "window.location.href.includes('show.do') || document.querySelector('#numeroProcesso')",
                        timeout=15000
                    )
                    # #region agent log
                    self._log_debug("scraper.py:_search_process:navigation_success", "Navegação bem-sucedida", {"url": page.url}, "C")
                    # #endregion
                    # Aguardar mais um pouco para garantir que a página carregou completamente
                    await page.wait_for_load_state('networkidle', timeout=10000)
                    # #region agent log
                    self._log_debug("scraper.py:_search_process:page_loaded", "Página carregada completamente", {"url": page.url}, "C")
                    # #endregion
                except Exception as e:
                    print(f"[DEBUG] Erro ao aguardar navegação: {e}", file=sys.stderr)
                    # #region agent log
                    self._log_debug("scraper.py:_search_process:navigation_error", "Erro ao aguardar navegação", {"error": str(e), "url": page.url}, "C")
                    # #endregion
                    # Aguardar um pouco mesmo em caso de erro
                    await page.wait_for_timeout(2000)
                
                # Obter URL atual
                current_url = page.url
                print(f"[DEBUG] URL após clique: {current_url}", file=sys.stderr)
                
                # #region agent log
                self._log_debug("scraper.py:_search_process:final_url", "URL final após navegação", {"current_url": current_url, "contains_show_do": "show.do" in current_url}, "C")
                # #endregion
                
                # Obter HTML da página
                html = await page.content()
                
                # Debug: salvar HTML dentro do diretório esaj_scraper
                debug_dir = Path(__file__).parent / "debug"
                debug_dir.mkdir(exist_ok=True)
                debug_file = debug_dir / f"playwright_result_{numero_processo.replace('.', '_').replace('-', '_')}.html"
                with open(debug_file, "w", encoding="utf-8") as f:
                    f.write(html)
                print(f"[DEBUG] HTML salvo em: {debug_file}", file=sys.stderr)
                
                # #region agent log
                self._log_debug("scraper.py:_search_process:html_saved", "HTML salvo para debug", {"debug_file": str(debug_file), "html_length": len(html)}, "C")
                # #endregion
                
                await browser.close()
                
                # Verificar se estamos na página de detalhes
                soup = BeautifulSoup(html, 'lxml')
                numero_processo_element = soup.find(id="numeroProcesso")
                print(f"[DEBUG] Elemento #numeroProcesso encontrado: {numero_processo_element is not None}", file=sys.stderr)
                
                # #region agent log
                self._log_debug("scraper.py:_search_process:element_check", "Verificação de elementos", {"numero_processo_element_found": numero_processo_element is not None, "contains_show_do": "show.do" in current_url}, "C")
                # #endregion
                
                if numero_processo_element or 'show.do' in current_url:
                    print(f"[DEBUG] Retornando URL: {current_url}", file=sys.stderr)
                    # #region agent log
                    self._log_debug("scraper.py:_search_process:success", "Busca bem-sucedida", {"url": current_url}, "C")
                    # #endregion
                    return current_url
                
                # Se não, procurar por links na página
                links = soup.find_all('a', href=re.compile(r'show\.do'))
                print(f"[DEBUG] Links encontrados: {len(links)}", file=sys.stderr)
                
                # #region agent log
                self._log_debug("scraper.py:_search_process:links_search", "Buscando links na página", {"links_count": len(links)}, "E")
                # #endregion
                
                if links:
                    href = links[0].get('href')
                    print(f"[DEBUG] Primeiro link: {href}", file=sys.stderr)
                    if href:
                        if href.startswith('http'):
                            # #region agent log
                            self._log_debug("scraper.py:_search_process:link_found", "Link encontrado (URL completa)", {"href": href}, "E")
                            # #endregion
                            return href
                        else:
                            full_url = f"{BASE_URL}{href}" if href.startswith('/') else f"{BASE_URL}/{href}"
                            print(f"[DEBUG] Retornando URL completa: {full_url}", file=sys.stderr)
                            # #region agent log
                            self._log_debug("scraper.py:_search_process:link_found", "Link encontrado (URL construída)", {"full_url": full_url}, "E")
                            # #endregion
                            return full_url
                
                print(f"[DEBUG] Nenhuma URL encontrada, retornando None", file=sys.stderr)
                # #region agent log
                self._log_debug("scraper.py:_search_process:failure", "Falha na busca - nenhuma URL encontrada", {"current_url": current_url}, "E")
                # #endregion
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

