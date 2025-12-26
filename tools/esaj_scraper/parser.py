"""Funções de parsing do HTML do portal e-SAJ."""

import re
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import List, Optional
from bs4 import BeautifulSoup
from .models import (
    InformacoesPrincipais,
    Parte,
    Advogado,
    Movimentacao,
    Peticao,
    Incidente,
)
from .config import SELECTORS

# #region agent log
LOG_PATH = "/home/ds/projects/ai_utils/.cursor/debug.log"

def _log_debug(location: str, message: str, data: dict, hypothesis_id: str = ""):
    """Helper para logging de debug."""
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


def clean_text(text: Optional[str]) -> str:
    """Remove espaços extras e limpa texto."""
    if not text:
        return ""
    return " ".join(text.strip().split())


def parse_process_header(html: str) -> InformacoesPrincipais:
    """Extrai informações principais do processo do HTML."""
    soup = BeautifulSoup(html, 'lxml')
    
    def get_text_by_id(element_id: str) -> Optional[str]:
        element = soup.find(id=element_id)
        if element:
            title = element.get('title', '')
            text = element.get_text()
            return clean_text(title or text)
        return None
    
    numero = get_text_by_id("numeroProcesso") or ""
    
    # Verificar tramitação prioritária
    tramitacao_prioritaria = bool(soup.select_one(SELECTORS["tramitacao_prioritaria"]))
    
    return InformacoesPrincipais(
        numero_processo=numero,
        classe=get_text_by_id("classeProcesso"),
        assunto=get_text_by_id("assuntoProcesso"),
        foro=get_text_by_id("foroProcesso"),
        vara=get_text_by_id("varaProcesso"),
        juiz=get_text_by_id("juizProcesso"),
        distribuicao=get_text_by_id("dataHoraDistribuicaoProcesso"),
        controle=get_text_by_id("numeroControleProcesso"),
        area=get_text_by_id("areaProcesso"),
        valor_acao=get_text_by_id("valorAcaoProcesso"),
        tramitacao_prioritaria=tramitacao_prioritaria,
    )


def parse_partes(html: str) -> List[Parte]:
    """Extrai partes do processo do HTML."""
    soup = BeautifulSoup(html, 'lxml')
    partes = []
    
    # #region agent log
    _log_debug("parser.py:parse_partes:entry", "Iniciando parse de partes", {}, "F")
    # #endregion
    
    tabela = soup.find(id="tablePartesPrincipais")
    if not tabela:
        # #region agent log
        _log_debug("parser.py:parse_partes:no_table", "Tabela de partes não encontrada", {}, "F")
        # #endregion
        return partes
    
    # #region agent log
    _log_debug("parser.py:parse_partes:table_found", "Tabela de partes encontrada", {}, "F")
    # #endregion
    
    rows = tabela.find_all('tr', class_='fundoClaro')
    
    # #region agent log
    _log_debug("parser.py:parse_partes:rows_found", "Linhas encontradas", {"rows_count": len(rows)}, "F")
    # #endregion
    
    rows = tabela.find_all('tr', class_='fundoClaro')
    for row in rows:
        cells = row.find_all('td')
        if len(cells) < 2:
            continue
        
        # Tipo está na primeira célula dentro de um span com classe tipoDeParticipacao
        tipo_elem = cells[0].find(class_='tipoDeParticipacao')
        tipo = clean_text(tipo_elem.get_text() if tipo_elem else "")
        
        # A segunda célula tem a classe nomeParteEAdvogado diretamente na <td>
        nome_cell = cells[1]
        if not nome_cell or 'nomeParteEAdvogado' not in nome_cell.get('class', []):
            continue
        
        # Extrair todo o texto da célula
        nome_text = nome_cell.get_text()
        
        # Separar nome da parte e advogados
        # O nome da parte vem antes de "Advogado:" ou é todo o texto se não houver advogado
        if 'Advogado:' in nome_text:
            partes_texto = nome_text.split('Advogado:')
            nome_parte = clean_text(partes_texto[0].strip())
            advogado_text = partes_texto[1].strip() if len(partes_texto) > 1 else ""
        else:
            nome_parte = clean_text(nome_text.strip())
            advogado_text = ""
        
        # Extrair advogados
        advogados = []
        # Procurar por "Advogado:" no texto da célula e extrair tudo após isso
        nome_cell_text = nome_cell.get_text()
        if 'Advogado:' in nome_cell_text:
            # Dividir pelo "Advogado:" e pegar a parte após
            partes_adv = nome_cell_text.split('Advogado:', 1)
            if len(partes_adv) > 1:
                adv_text_raw = partes_adv[1].strip()
                # Limpar o texto do advogado
                adv_text = clean_text(adv_text_raw)
                
                if adv_text:
                    # Tentar extrair OAB do formato "Nome (OAB 12345/SP)"
                    oab_match = re.search(r'OAB\s*(\d+[\/\-]?\w*)', adv_text, re.IGNORECASE)
                    oab = oab_match.group(1) if oab_match else None
                    
                    # Remover OAB do nome
                    nome_adv = re.sub(r'\s*\(?OAB\s*\d+[\/\-]?\w*\)?', '', adv_text).strip()
                    
                    if nome_adv:
                        advogados.append(Advogado(nome=nome_adv, oab=oab))
        
        if nome_parte:
            # #region agent log
            _log_debug("parser.py:parse_partes:parte_found", "Parte encontrada", {"tipo": tipo, "nome": nome_parte, "advogados_count": len(advogados)}, "F")
            # #endregion
            partes.append(Parte(
                tipo_participacao=tipo,
                nome=nome_parte,
                advogados=advogados
            ))
        else:
            # #region agent log
            _log_debug("parser.py:parse_partes:parte_skipped", "Parte ignorada (sem nome)", {"tipo": tipo}, "F")
            # #endregion
    
    # #region agent log
    _log_debug("parser.py:parse_partes:result", "Parse de partes concluído", {"partes_count": len(partes)}, "F")
    # #endregion
    
    return partes


def parse_movimentacoes(html: str) -> List[Movimentacao]:
    """Extrai movimentações processuais do HTML."""
    soup = BeautifulSoup(html, 'lxml')
    movimentacoes = []
    
    # #region agent log
    _log_debug("parser.py:parse_movimentacoes:entry", "Iniciando parse de movimentações", {}, "G")
    # #endregion
    
    # Tentar pegar todas as movimentações primeiro
    tabela = soup.find(id="tabelaTodasMovimentacoes")
    if not tabela:
        tabela = soup.find(id="tabelaUltimasMovimentacoes")
    
    if not tabela:
        # #region agent log
        _log_debug("parser.py:parse_movimentacoes:no_table", "Tabela de movimentações não encontrada", {}, "G")
        # #endregion
        return movimentacoes
    
    # #region agent log
    _log_debug("parser.py:parse_movimentacoes:table_found", "Tabela de movimentações encontrada", {"table_id": tabela.get('id')}, "G")
    # #endregion
    
    rows = tabela.find_all('tr', class_=lambda x: x and 'containerMovimentacao' in x)
    
    # #region agent log
    _log_debug("parser.py:parse_movimentacoes:rows_found", "Linhas encontradas", {"rows_count": len(rows)}, "G")
    # #endregion
    
    for row in rows:
        cells = row.find_all('td')
        if len(cells) < 3:
            continue
        
        # Data (primeira coluna com classe dataMovimentacao)
        data_cell = cells[0]
        data = clean_text(data_cell.get_text())
        
        # Descrição está na terceira coluna (cells[2]) que tem classe descricaoMovimentacao
        desc_cell = cells[2]
        if 'descricaoMovimentacao' not in desc_cell.get('class', []):
            continue
        
        # Tipo (primeiro link ou primeiro texto não vazio)
        tipo = ""
        tipo_elem = desc_cell.find('a')
        if tipo_elem:
            tipo = clean_text(tipo_elem.get_text())
        else:
            # Procurar por texto direto (pode estar em um span ou div)
            texto_elem = desc_cell.find(string=re.compile(r'\S+'))
            if texto_elem:
                # Pegar o texto até a primeira quebra de linha ou tag <br>
                tipo = clean_text(texto_elem.strip())
        
        # Se ainda não encontrou tipo, pegar todo o texto e remover detalhes
        if not tipo:
            tipo = clean_text(desc_cell.get_text())
            # Remover detalhes em itálico se houver
            tipo = tipo.split('\n')[0].strip()
        
        # Detalhes (texto em itálico - span com style italic)
        detalhes = None
        detalhes_elem = desc_cell.find('span', style=lambda x: x and 'italic' in str(x).lower() if x else False)
        if detalhes_elem:
            detalhes = clean_text(detalhes_elem.get_text())
        
        # Link para documento (pode estar na segunda coluna ou dentro da descrição)
        link_documento = None
        link_elem = cells[1].find('a') if len(cells) > 1 else None
        if not link_elem:
            link_elem = desc_cell.find('a')
        
        if link_elem and link_elem.get('href'):
            href = link_elem.get('href')
            if href and not href.startswith('#'):
                link_documento = href
            elif href == '#liberarAutoPorSenha':
                # Link pode estar no onclick
                onclick = link_elem.get('onclick', '')
                # Extrair URL do onclick se disponível
                link_documento = href
        
        if data or tipo:
            # #region agent log
            _log_debug("parser.py:parse_movimentacoes:mov_found", "Movimentação encontrada", {"data": data, "tipo": tipo, "detalhes": detalhes}, "G")
            # #endregion
            movimentacoes.append(Movimentacao(
                data=data,
                tipo=tipo,
                detalhes=detalhes,
                link_documento=link_documento
            ))
        else:
            # #region agent log
            _log_debug("parser.py:parse_movimentacoes:mov_skipped", "Movimentação ignorada (sem data ou tipo)", {"cells_count": len(cells)}, "G")
            # #endregion
    
    # #region agent log
    _log_debug("parser.py:parse_movimentacoes:result", "Parse de movimentações concluído", {"movimentacoes_count": len(movimentacoes)}, "G")
    # #endregion
    
    return movimentacoes


def parse_peticoes(html: str) -> List[Peticao]:
    """Extrai petições diversas do HTML."""
    soup = BeautifulSoup(html, 'lxml')
    peticoes = []
    
    # Procurar pela tabela de petições (procura por seção "Petições diversas")
    sections = soup.find_all('h2', class_='subtitle')
    for section in sections:
        if 'Petições diversas' in section.get_text():
            # Encontrar a tabela seguinte
            tabela = section.find_next('table')
            if tabela:
                rows = tabela.find('tbody')
                if rows:
                    for row in rows.find_all('tr'):
                        cells = row.find_all('td')
                        if len(cells) >= 2:
                            data = clean_text(cells[0].get_text())
                            tipo = clean_text(cells[1].get_text())
                            if data and tipo:
                                peticoes.append(Peticao(data=data, tipo=tipo))
                break
    
    return peticoes


def parse_incidentes(html: str) -> List[Incidente]:
    """Extrai incidentes, apensos e processos relacionados do HTML."""
    soup = BeautifulSoup(html, 'lxml')
    incidentes = []
    
    # Procurar pela seção de incidentes
    sections = soup.find_all('h2', class_='subtitle')
    for section in sections:
        text = section.get_text()
        if 'Incidentes' in text or 'Apensos' in text:
            tabela = section.find_next('table')
            if tabela:
                rows = tabela.find('tbody')
                if rows:
                    for row in rows.find_all('tr'):
                        cells = row.find_all('td')
                        if len(cells) >= 2:
                            data_recebimento = clean_text(cells[0].get_text())
                            
                            # Classe ou número do processo
                            classe_elem = cells[1]
                            classe = clean_text(classe_elem.get_text())
                            
                            # Tentar extrair número do processo se houver link
                            link = classe_elem.find('a')
                            numero_processo = None
                            tipo = None
                            
                            if link:
                                numero_processo = clean_text(link.get_text())
                                # Tipo pode estar no texto antes do link
                                tipo = clean_text(classe_elem.get_text().replace(numero_processo, '').strip())
                            
                            if data_recebimento:
                                incidentes.append(Incidente(
                                    data_recebimento=data_recebimento,
                                    classe=classe,
                                    numero_processo=numero_processo,
                                    tipo=tipo
                                ))
                break
    
    return incidentes



