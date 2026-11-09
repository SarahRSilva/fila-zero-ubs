"""Validação de entrada e formato das respostas."""
from __future__ import annotations

from datetime import date, datetime, time
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from . import config

Turno = Literal["manha", "tarde", "noite"]
Cor = Literal["verde", "amarelo", "vermelho"]


class LoginEntrada(BaseModel):
    email: str = Field(min_length=5, max_length=120, pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
    senha: str = Field(min_length=1, max_length=72)


class LoginSaida(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expira_em_min: int
    nome: str
    perfil: str
    ubs: str | None


class CadastroEntrada(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    nome: str = Field(min_length=2, max_length=80)
    email: str = Field(min_length=5, max_length=120, pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
    senha: str = Field(min_length=8, max_length=72)


class AtendimentoEntrada(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    ubs: str
    data: date
    turno: Turno
    motivo: str = Field(min_length=3, max_length=200)
    cor_triagem: Cor
    hora_chegada: time | None = None
    hora_atendimento: time | None = None
    espera_min: int | None = Field(default=None, ge=0, le=24 * 60, description="Minutos de espera; nunca negativo")
    atendido: bool = False

    @field_validator("ubs")
    @classmethod
    def ubs_existe(cls, v: str) -> str:
        if v not in config.UBS:
            raise ValueError(f"UBS desconhecida. Opções: {', '.join(config.UBS)}")
        return v

    @model_validator(mode="after")
    def horarios_coerentes(self):
        if self.hora_chegada and self.hora_atendimento and self.hora_atendimento < self.hora_chegada:
            raise ValueError("hora_atendimento não pode ser anterior a hora_chegada")
        if self.atendido and (self.hora_atendimento is None or self.espera_min is None):
            raise ValueError("atendimento concluído exige hora_atendimento e espera_min")
        return self


class AtendimentoSaida(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    cidadao_hash: str
    ubs: str
    data: date
    turno: str
    motivo: str
    cor_triagem: str
    hora_chegada: time | None
    hora_atendimento: time | None
    espera_min: int | None
    atendido: bool
    criado_em: datetime


class PrevisaoSaida(BaseModel):
    data: date
    ubs: str
    aberta: bool
    motivo_fechada: str | None
    turnos: dict[str, int]
    modelo: str
    mae_teste: float


class TriagemEntrada(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    relato: str = Field(min_length=1, max_length=600, description="O que o cidadão escreveu")
    resposta_anterior: str | None = Field(default=None, max_length=200,
                                          description="Resposta à pergunta de esclarecimento, se houve")


class TriagemSaida(BaseModel):
    cor: Cor
    motivo_resumido: str
    turno_sugerido: Literal["manha", "tarde", "noite", "agora"]
    orientacao: str
    pergunta: str | None


class LeituraSalaEntrada(BaseModel):
    """Mesmo JSON que o sensor publica no MQTT, para quem não tem broker."""
    ubs: str
    ocupacao: int = Field(ge=0, le=500)
    capacidade: int = Field(gt=0, le=500)
    temperatura: float | None = Field(default=None, ge=-10, le=60)
    entradas: int | None = None
    saidas: int | None = None
    alerta: bool | None = None
    origem: str = Field(default="api", max_length=20)
    ts: datetime | None = None

    @field_validator("ubs")
    @classmethod
    def ubs_existe(cls, v: str) -> str:
        if v not in config.UBS:
            raise ValueError(f"UBS desconhecida. Opções: {', '.join(config.UBS)}")
        return v


class SalaAgora(BaseModel):
    ubs: str
    ocupacao: int
    capacidade: int
    taxa_ocupacao: float
    alerta: bool
    temperatura: float | None
    origem: str
    ts: datetime
    segundos_atras: int
    alertas_hoje: int
