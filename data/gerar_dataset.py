"""Gera o dataset SINTÉTICO do Fila Zero UBS.

Nada aqui é dado real de paciente ou de UBS: os números são simulados com
sazonalidade plausível (mais demanda na segunda-feira, em semanas de chuva,
nos meses de dengue e no inverno) para treinar o modelo e alimentar o lake.

Uso:
    python data/gerar_dataset.py                      # 12 meses padrão
    python data/gerar_dataset.py --inicio 2026-01-01 --fim 2026-03-31

Saídas:
    bigdata/lake/bronze/atendimentos_YYYY-MM.csv   uma linha por pessoa que foi à UBS
    bigdata/lake/bronze/clima_diario.csv           temperatura máxima e chuva por dia
    bigdata/lake/bronze/feriados.csv               feriados nacionais do período
    bigdata/lake/bronze/lotacao_YYYY-MM.csv        leituras do sensor da sala de espera a cada 10 min
    data/demanda_turno.csv                         agregado por dia/turno/UBS (treino da IA)
"""
from __future__ import annotations

import argparse
import hashlib
import heapq
from datetime import date, datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

RAIZ = Path(__file__).resolve().parents[1]

# Feriados nacionais do período padrão. A UBS não abre nesses dias.
FERIADOS = {
    date(2025, 11, 2), date(2025, 11, 15), date(2025, 11, 20), date(2025, 12, 25),
    date(2026, 1, 1), date(2026, 2, 16), date(2026, 2, 17), date(2026, 4, 3),
    date(2026, 4, 21), date(2026, 5, 1), date(2026, 6, 4), date(2026, 9, 7),
    date(2026, 10, 12), date(2026, 11, 2), date(2026, 11, 15), date(2026, 11, 20),
    date(2026, 12, 25),
}

# UBS fictícias: fator de porte multiplica a demanda e define a equipe.
UBS = {
    "UBS Jardim Esperanca": {"porte": 1.0, "equipe": {"manha": 4, "tarde": 3, "noite": 2}, "cadeiras": 30},
    "UBS Vila Nova": {"porte": 0.7, "equipe": {"manha": 3, "tarde": 2, "noite": 1}, "cadeiras": 20},
}
LEITURA_MIN = 10  # intervalo das leituras sintéticas do sensor da sala

# Por turno: demanda base, janela de atendimento e janela em que as pessoas chegam.
# Na fila por ordem de chegada, quem quer a manhã chega a partir das 5h.
TURNOS = {
    "manha": {"base": 60, "abre": 7.0, "fecha": 12.0, "chega_de": 5.0, "chega_ate": 10.5, "pico": 6.0},
    "tarde": {"base": 45, "abre": 13.0, "fecha": 17.0, "chega_de": 11.5, "chega_ate": 16.0, "pico": 12.75},
    "noite": {"base": 20, "abre": 18.0, "fecha": 21.0, "chega_de": 17.0, "chega_ate": 20.25, "pico": 17.75},
}

FATOR_DIA = {0: 1.30, 1: 1.10, 2: 1.00, 3: 0.95, 4: 0.90}  # segunda a sexta
# dengue (fev-mai) e síndromes respiratórias de inverno (jun-ago)
FATOR_MES = {1: 1.00, 2: 1.10, 3: 1.25, 4: 1.30, 5: 1.15, 6: 1.15, 7: 1.20, 8: 1.10,
             9: 1.00, 10: 0.95, 11: 0.95, 12: 0.90}
CHUVA_SEMANA_MM = 60     # acima disso nos últimos 7 dias conta como "semana de chuva"
FATOR_SEMANA_CHUVA = 1.10
FATOR_POS_FERIADO = 1.15
ATENDIMENTO_MEDIO_MIN = 14

MOTIVOS = {
    "verde": ["renovacao de receita", "vacina", "coleta de exame", "acompanhamento de hipertensao",
              "acompanhamento de diabetes", "pre-natal", "curativo de rotina", "puericultura"],
    "amarelo": ["febre ha 3 dias", "dor forte", "ferida infectada", "vomito e diarreia",
                "tosse persistente", "suspeita de dengue", "dor de ouvido em crianca"],
    "vermelho": ["dor no peito", "falta de ar intensa", "sangramento que nao para",
                 "confusao mental", "febre alta em bebe"],
}


def gerar_clima(dias: pd.DatetimeIndex, rng: np.random.Generator) -> pd.DataFrame:
    """Clima plausível para o Sudeste: verão quente e chuvoso, inverno seco."""
    doy = dias.day_of_year.to_numpy()
    verao = np.cos(2 * np.pi * (doy - 20) / 365)  # +1 em janeiro, -1 em julho
    temp_max = 25.5 + 4.0 * verao + rng.normal(0, 2.5, len(dias))
    p_chuva = 0.30 + 0.25 * verao
    choveu = rng.random(len(dias)) < p_chuva
    chuva_mm = np.where(choveu, rng.gamma(1.6, 9.0, len(dias)) * (1 + 0.5 * verao.clip(0)), 0.0)
    return pd.DataFrame({"data": dias.date, "temp_max": temp_max.round(1), "chuva_mm": chuva_mm.round(1)})


def cpf_hash(ubs: str, n: int) -> str:
    """Identificador pseudonimizado. Nem aqui existe CPF: é o hash de um número fictício."""
    return hashlib.sha256(f"{ubs}-{n}".encode()).hexdigest()[:16]


def hhmm(dia: date, horas: float) -> str:
    return (datetime.combine(dia, datetime.min.time()) + timedelta(hours=float(horas))).strftime("%H:%M")


def simular_turno(dia, ubs, turno, n, mes, rng):
    """Fila por ordem de chegada com `equipe` profissionais. Quem não é chamado
    até 30 min depois do fim do turno volta para casa sem atendimento."""
    cfg, info = TURNOS[turno], UBS[ubs]
    # chegadas concentradas antes da abertura, com cauda ao longo do turno
    chegadas = np.sort(np.clip(
        rng.gamma(2.0, 0.75, n) + cfg["pico"] - 1.0, cfg["chega_de"], cfg["chega_ate"]))
    livres = [cfg["abre"]] * info["equipe"][turno]
    heapq.heapify(livres)
    limite = cfg["fecha"] + 0.5

    p_amarelo = 0.25 + (0.08 if mes in (3, 4, 5, 6, 7) else 0.0)
    cores = rng.choice(["verde", "amarelo", "vermelho"], n, p=[0.96 - p_amarelo, p_amarelo, 0.04])
    populacao = int(6000 * info["porte"])

    linhas = []
    for chegada, cor in zip(chegadas, cores, strict=True):
        inicio = max(chegada, livres[0])
        atendido = inicio <= limite
        if atendido:
            duracao = float(np.clip(rng.exponential(ATENDIMENTO_MEDIO_MIN), 5, 40)) / 60
            heapq.heapreplace(livres, inicio + duracao)
        linhas.append({
            "cpf_hash": cpf_hash(ubs, int(rng.integers(populacao))),
            "ubs": ubs,
            "data": dia.isoformat(),
            "turno": turno,
            "hora_chegada": hhmm(dia, chegada),
            "hora_atendimento": hhmm(dia, inicio) if atendido else "",
            "espera_min": int(round((inicio - chegada) * 60)) if atendido else "",
            "motivo": rng.choice(MOTIVOS[cor]),
            "cor_triagem": cor,
            "atendido": "S" if atendido else "N",
        })
    return linhas


def gerar(inicio: date, fim: date, seed: int = 42):
    """Devolve (atendimentos, clima, demanda_por_turno) como DataFrames."""
    rng = np.random.default_rng(seed)
    dias = pd.date_range(inicio, fim, freq="D")
    clima = gerar_clima(dias, rng)
    chuva_7d = clima["chuva_mm"].rolling(7, min_periods=1).sum().shift(1).fillna(0)

    linhas, demanda = [], []
    for i, dia in enumerate(clima["data"]):
        if dia.weekday() > 4 or dia in FERIADOS:
            continue
        ontem_util = dia - timedelta(days=3 if dia.weekday() == 0 else 1)
        pos_feriado = ontem_util in FERIADOS
        semana_chuva = chuva_7d.iloc[i] > CHUVA_SEMANA_MM
        fator = (FATOR_DIA[dia.weekday()] * FATOR_MES[dia.month]
                 * (FATOR_SEMANA_CHUVA if semana_chuva else 1.0)
                 * (FATOR_POS_FERIADO if pos_feriado else 1.0))
        for ubs, info in UBS.items():
            for turno, cfg in TURNOS.items():
                n = int(rng.poisson(cfg["base"] * info["porte"] * fator))
                linhas.extend(simular_turno(dia, ubs, turno, n, dia.month, rng))
                demanda.append({
                    "data": dia.isoformat(), "ubs": ubs, "turno": turno, "procura": n,
                    "dia_semana": dia.weekday(), "mes": dia.month,
                    "pos_feriado": int(pos_feriado), "temp_max": clima["temp_max"].iloc[i],
                    "chuva_mm": clima["chuva_mm"].iloc[i], "chuva_7d_mm": round(float(chuva_7d.iloc[i]), 1),
                })

    atend = pd.DataFrame(linhas)
    atend.insert(0, "id", range(1, len(atend) + 1))
    dem = pd.DataFrame(demanda)
    if not atend.empty:
        ok = (atend[atend["atendido"] == "S"].groupby(["data", "ubs", "turno"]).size()
              .rename("atendidos").reset_index())
        dem = dem.merge(ok, how="left", on=["data", "ubs", "turno"])
        dem["atendidos"] = dem["atendidos"].fillna(0).astype(int)
    return atend, clima, dem


def gerar_lotacao(atend: pd.DataFrame, clima: pd.DataFrame, rng: np.random.Generator) -> pd.DataFrame:
    """Leituras do sensor da sala a cada 10 min: quem já chegou e ainda não foi atendido
    (ou saiu sem atendimento) está na sala. Acima das cadeiras, fica gente em pé."""
    if atend.empty:
        return pd.DataFrame()
    temp_dia = dict(zip(clima["data"].astype(str), clima["temp_max"], strict=True))
    chegada = pd.to_datetime(atend["data"] + " " + atend["hora_chegada"])
    saida = pd.to_datetime(atend["data"] + " " + atend["hora_atendimento"].where(atend["atendido"] == "S", ""),
                           errors="coerce")
    # quem não foi atendido vai embora 30 min depois do fim do turno em que chegou
    fim_turno = atend["turno"].map({t: cfg["fecha"] + 0.5 for t, cfg in TURNOS.items()})
    saida = saida.fillna(pd.to_datetime(atend["data"]) + pd.to_timedelta(fim_turno, unit="h"))
    base = pd.DataFrame({"ubs": atend["ubs"], "dia": atend["data"], "chegada": chegada, "saida": saida})

    linhas = []
    for (ubs, dia), grupo in base.groupby(["ubs", "dia"]):
        cadeiras = UBS[ubs]["cadeiras"]
        instantes = pd.date_range(f"{dia} 05:00", f"{dia} 21:30", freq=f"{LEITURA_MIN}min")
        ch, sd = grupo["chegada"].to_numpy(), grupo["saida"].to_numpy()
        dentro = ((ch[None, :] <= instantes.to_numpy()[:, None]) & (sd[None, :] > instantes.to_numpy()[:, None])).sum(1)
        entradas = (ch[None, :] <= instantes.to_numpy()[:, None]).sum(1)
        horas = instantes.hour + instantes.minute / 60
        temp = temp_dia.get(dia, 26.0) - 5 + 5 * np.exp(-((horas - 15) ** 2) / 18) + 0.08 * dentro
        for i, inst in enumerate(instantes):
            oc = int(dentro[i] + rng.integers(-1, 2))
            oc = max(0, oc)
            linhas.append({
                "ts": inst.strftime("%Y-%m-%dT%H:%M:00-03:00"), "ubs": ubs, "ocupacao": oc, "capacidade": cadeiras,
                "temperatura": round(float(temp[i] + rng.normal(0, 0.2)), 1),
                "entradas": int(entradas[i]), "saidas": int(entradas[i] - dentro[i]),
                "alerta": "S" if oc >= cadeiras * 0.9 else "N", "origem": "sintetico",
            })
    return pd.DataFrame(linhas)


def salvar(atend: pd.DataFrame, clima: pd.DataFrame, dem: pd.DataFrame, raiz: Path = RAIZ,
           lotacao: pd.DataFrame | None = None) -> None:
    bronze = raiz / "bigdata" / "lake" / "bronze"
    bronze.mkdir(parents=True, exist_ok=True)
    for mes, parte in atend.groupby(atend["data"].str[:7]):
        parte.to_csv(bronze / f"atendimentos_{mes}.csv", index=False)
    clima.to_csv(bronze / "clima_diario.csv", index=False)
    pd.DataFrame({"data": sorted(d.isoformat() for d in FERIADOS)}).to_csv(bronze / "feriados.csv", index=False)
    if lotacao is not None and not lotacao.empty:
        for mes, parte in lotacao.groupby(lotacao["ts"].str[:7]):
            parte.to_csv(bronze / f"lotacao_{mes}.csv", index=False)
    (raiz / "data").mkdir(exist_ok=True)
    dem.to_csv(raiz / "data" / "demanda_turno.csv", index=False)


def main() -> None:
    ap = argparse.ArgumentParser(description="Gera o dataset sintético do Fila Zero UBS")
    ap.add_argument("--inicio", default="2025-11-01")
    ap.add_argument("--fim", default="2026-10-31")
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()

    atend, clima, dem = gerar(date.fromisoformat(args.inicio), date.fromisoformat(args.fim), args.seed)
    lotacao = gerar_lotacao(atend, clima, np.random.default_rng(args.seed + 1))
    salvar(atend, clima, dem, lotacao=lotacao)
    atendidos = atend[atend["atendido"] == "S"]
    print(f"{len(atend):,} idas à UBS em {dem['data'].nunique()} dias úteis ({args.inicio} a {args.fim})")
    print(f"espera média: {atendidos['espera_min'].astype(int).mean():.0f} min | "
          f"voltaram sem atendimento: {(atend['atendido'] == 'N').mean():.1%}")
    print(f"{len(lotacao):,} leituras do sensor da sala | "
          f"em alerta (>= 90% das cadeiras): {(lotacao['alerta'] == 'S').mean():.1%}")


if __name__ == "__main__":
    main()
