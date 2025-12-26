"""Modelos de dados Pydantic para processos do e-SAJ."""

from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field


class Advogado(BaseModel):
    """Representa um advogado."""
    nome: str
    oab: Optional[str] = None


class Parte(BaseModel):
    """Representa uma parte do processo."""
    tipo_participacao: str = Field(..., description="Tipo de participação (ex: Reqte, Reqdo)")
    nome: str
    advogados: List[Advogado] = Field(default_factory=list)


class Movimentacao(BaseModel):
    """Representa uma movimentação processual."""
    data: str
    tipo: str
    detalhes: Optional[str] = None
    link_documento: Optional[str] = None


class Peticao(BaseModel):
    """Representa uma petição."""
    data: str
    tipo: str


class Incidente(BaseModel):
    """Representa um incidente ou processo relacionado."""
    data_recebimento: str
    classe: str
    numero_processo: Optional[str] = None
    tipo: Optional[str] = None


class InformacoesPrincipais(BaseModel):
    """Informações principais do processo."""
    numero_processo: str
    classe: Optional[str] = None
    assunto: Optional[str] = None
    foro: Optional[str] = None
    vara: Optional[str] = None
    juiz: Optional[str] = None
    distribuicao: Optional[str] = None
    controle: Optional[str] = None
    area: Optional[str] = None
    valor_acao: Optional[str] = None
    tramitacao_prioritaria: bool = False


class Metadata(BaseModel):
    """Metadados da extração."""
    data_extracao: datetime
    status: str
    erro: Optional[str] = None


class ProcessoCompleto(BaseModel):
    """Modelo completo do processo com todos os dados extraídos."""
    informacoes_principais: InformacoesPrincipais
    partes: List[Parte] = Field(default_factory=list)
    movimentacoes: List[Movimentacao] = Field(default_factory=list)
    peticoes: List[Peticao] = Field(default_factory=list)
    incidentes: List[Incidente] = Field(default_factory=list)
    metadata: Metadata

    def to_json_dict(self) -> dict:
        """Converte o modelo para dicionário JSON-serializable."""
        return self.model_dump(mode='json')



