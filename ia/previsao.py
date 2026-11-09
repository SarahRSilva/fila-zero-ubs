"""Previsão de demanda por turno: montagem das variáveis e uso do modelo treinado.

O treino fica em ia/treinar.py. Este módulo é o que a API importa.
"""
from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

import joblib
import pandas as pd

RAIZ = Path(__file__).resolve().parents[1]
CAMINHO_MODELO = RAIZ / "ia" / "modelo" / "previsao_demanda.pkl"

TURNOS = ["manha", "tarde", "noite"]
VARIAVEIS = [
    "ubs_cod", "turno_cod", "dia_semana", "mes", "pos_feriado",
    "temp_max", "chuva_mm", "chuva_7d_mm", "media_movel_7d",
]
CLIMA = ["temp_max", "chuva_mm", "chuva_7d_mm"]
JANELA = 7  # dias de funcionamento usados na média móvel


def montar_base(demanda: pd.DataFrame, dim_data: pd.DataFrame, lista_ubs: list[str]) -> pd.DataFrame:
    """Junta a procura por (data, ubs, turno) com o calendário e o clima.

    A média móvel usa só os 7 dias de funcionamento ANTERIORES (shift), para o
    modelo nunca ver o valor que está tentando prever.
    """
    base = demanda.merge(dim_data, on="data", how="left").sort_values(["ubs", "turno", "data"])
    base["media_movel_7d"] = base.groupby(["ubs", "turno"])["procura"].transform(
        lambda s: s.shift(1).rolling(JANELA, min_periods=1).mean()
    )
    base["ubs_cod"] = base["ubs"].map({u: i for i, u in enumerate(lista_ubs)})
    base["turno_cod"] = base["turno"].map({t: i for i, t in enumerate(TURNOS)})
    return base.dropna(subset=["media_movel_7d"]).reset_index(drop=True)


def dia_util_anterior(dia: date) -> date:
    return dia - timedelta(days=3 if dia.weekday() == 0 else 1)


class Previsor:
    """Modelo treinado mais as tabelas de apoio para prever uma data qualquer."""

    def __init__(self, artefato: dict):
        self.modelo = artefato["modelo"]
        self.lista_ubs: list[str] = artefato["lista_ubs"]
        self.historico: dict = artefato["historico"]  # (ubs, turno) -> [(data, procura), ...] em ordem de data
        self.clima: dict = artefato["clima"]          # data -> clima observado
        self.normais: dict = artefato["normais"]      # mês -> média do clima
        self.feriados: set[date] = set(artefato["feriados"])
        self.metricas: dict = artefato["metricas"]

    @classmethod
    def carregar(cls, caminho: Path = CAMINHO_MODELO) -> "Previsor":
        return cls(joblib.load(caminho))

    def motivo_fechada(self, dia: date) -> str | None:
        if dia.weekday() > 4:
            return "fim de semana"
        if dia in self.feriados:
            return "feriado"
        return None

    def prever(self, dia: date, ubs: str, temp_max: float | None = None,
               chuva_mm: float | None = None) -> dict[str, int]:
        """Procura prevista em cada turno. Em dia sem expediente devolve zero.

        Sem previsão do tempo informada, usa o clima observado (data do
        histórico) ou a média do mês (data futura).
        """
        if ubs not in self.lista_ubs:
            raise ValueError(f"UBS desconhecida: {ubs}")
        if self.motivo_fechada(dia):
            return {t: 0 for t in TURNOS}

        clima = dict(self.clima.get(dia) or self.normais[dia.month])
        if temp_max is not None:
            clima["temp_max"] = temp_max
        if chuva_mm is not None:
            clima["chuva_mm"] = chuva_mm

        linhas = []
        for turno in TURNOS:
            ultimos = [procura for data, procura in self.historico.get((ubs, turno), []) if data < dia][-JANELA:]
            linhas.append({
                "ubs_cod": self.lista_ubs.index(ubs),
                "turno_cod": TURNOS.index(turno),
                "dia_semana": dia.weekday(),
                "mes": dia.month,
                "pos_feriado": int(dia_util_anterior(dia) in self.feriados),
                **clima,
                "media_movel_7d": sum(ultimos) / len(ultimos) if ultimos else 0.0,
            })
        previsto = self.modelo.predict(pd.DataFrame(linhas)[VARIAVEIS])
        return {t: max(0, int(round(float(v)))) for t, v in zip(TURNOS, previsto, strict=True)}
