"""Treina o modelo de previsão de demanda por turno com os dados do gold.

Uso (depois de rodar bigdata/pipeline.py):
    python ia/treinar.py

Como o modelo é escolhido e medido:
    - teste     = últimos 30 dias do histórico; nenhum modelo vê esses dias antes da medição
    - validação = os 30 dias anteriores ao teste; serve só para escolher entre os candidatos
    - o candidato escolhido é reajustado em treino + validação e medido no teste
    - o modelo salvo para a API é reajustado depois com o histórico inteiro

Saídas:
    ia/modelo/previsao_demanda.pkl             modelo + tabelas de apoio (usado pela API)
    ia/modelo/metricas.json                    MAE por turno, linha de base e meta
    bigdata/lake/gold/fato_previsao.parquet    previsto x real por data, UBS e turno
"""
from __future__ import annotations

import json
import sys
from datetime import timedelta
from pathlib import Path

import joblib
import pandas as pd
from sklearn.ensemble import GradientBoostingRegressor, RandomForestRegressor
from sklearn.metrics import mean_absolute_error

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

from ia.previsao import CAMINHO_MODELO, CLIMA, TURNOS, VARIAVEIS, montar_base  # noqa: E402

GOLD = RAIZ / "bigdata" / "lake" / "gold"
DIAS_TESTE = 30
META_PCT = 15.0  # MAE abaixo de 15% da média do turno

CANDIDATOS = {
    "RandomForest": lambda: RandomForestRegressor(n_estimators=300, min_samples_leaf=3, random_state=42),
    "GradientBoosting": lambda: GradientBoostingRegressor(
        n_estimators=300, max_depth=3, learning_rate=0.05, subsample=0.8, random_state=42),
}


def carregar_gold(gold: Path = GOLD) -> tuple[pd.DataFrame, pd.DataFrame, list[str], list]:
    fato = pd.read_parquet(gold / "fato_atendimento.parquet", columns=["data", "ubs", "turno"])
    dim_data = pd.read_parquet(gold / "dim_data.parquet")
    lista_ubs = sorted(pd.read_parquet(gold / "dim_ubs.parquet")["ubs"])
    demanda = fato.groupby(["data", "ubs", "turno"]).size().rename("procura").reset_index()
    feriados = sorted(pd.read_parquet(gold / "dim_feriado.parquet")["data"])
    return demanda, dim_data, lista_ubs, feriados


def medir(real: pd.Series, previsto, turnos: pd.Series) -> dict:
    """MAE geral e por turno, com o percentual sobre a média do turno."""
    por_turno = {}
    for turno in TURNOS:
        m = turnos == turno
        mae = float(mean_absolute_error(real[m], previsto[m]))
        media = float(real[m].mean())
        por_turno[turno] = {
            "mae": round(mae, 2), "media": round(media, 1),
            "pct_da_media": round(100 * mae / media, 1), "meta_ok": bool(100 * mae / media < META_PCT),
        }
    return {"mae_geral": round(float(mean_absolute_error(real, previsto)), 2), "por_turno": por_turno}


def treinar(gold: Path = GOLD, caminho_modelo: Path = CAMINHO_MODELO) -> dict:
    demanda, dim_data, lista_ubs, feriados = carregar_gold(gold)
    base = montar_base(demanda, dim_data, lista_ubs)

    fim = base["data"].max()
    inicio_teste = fim - timedelta(days=DIAS_TESTE - 1)
    inicio_val = inicio_teste - timedelta(days=DIAS_TESTE)
    treino = base[base["data"] < inicio_val]
    val = base[(base["data"] >= inicio_val) & (base["data"] < inicio_teste)]
    teste = base[base["data"] >= inicio_teste]
    antes_do_teste = base[base["data"] < inicio_teste]

    mae_val = {}
    for nome, fabrica in CANDIDATOS.items():
        m = fabrica().fit(treino[VARIAVEIS], treino["procura"])
        mae_val[nome] = round(float(mean_absolute_error(val["procura"], m.predict(val[VARIAVEIS]))), 2)
    escolhido = min(mae_val, key=mae_val.get)

    modelo = CANDIDATOS[escolhido]().fit(antes_do_teste[VARIAVEIS], antes_do_teste["procura"])
    previsto_teste = modelo.predict(teste[VARIAVEIS])

    metricas = {
        "modelo": escolhido,
        "mae_validacao_por_candidato": mae_val,
        "periodo_treino": [str(antes_do_teste["data"].min()), str(antes_do_teste["data"].max())],
        "periodo_teste": [str(teste["data"].min()), str(teste["data"].max())],
        "linhas_treino": int(len(antes_do_teste)),
        "linhas_teste": int(len(teste)),
        "meta_pct_da_media": META_PCT,
        "teste": medir(teste["procura"], previsto_teste, teste["turno"]),
        "linha_de_base_media_movel_7d": medir(teste["procura"], teste["media_movel_7d"].to_numpy(), teste["turno"]),
        "dados": "sintéticos (data/gerar_dataset.py)",
    }

    # previsto x real para o dashboard: no período de teste a previsão é de um
    # modelo que não viu aqueles dias; no restante é ajuste dentro do treino.
    fato_prev = pd.concat([
        antes_do_teste.assign(previsto=modelo.predict(antes_do_teste[VARIAVEIS]), conjunto="treino"),
        teste.assign(previsto=previsto_teste, conjunto="teste"),
    ])[["data", "ubs", "turno", "procura", "previsto", "conjunto"]].rename(columns={"procura": "real"})
    fato_prev["previsto"] = fato_prev["previsto"].round().clip(lower=0).astype(int)
    fato_prev.to_parquet(gold / "fato_previsao.parquet", index=False)

    # modelo que vai para a API: mesmo algoritmo, reajustado com tudo
    final = CANDIDATOS[escolhido]().fit(base[VARIAVEIS], base["procura"])
    # as tabelas de apoio vão como dicionários comuns, para o arquivo não depender da versão do pandas
    ordenada = demanda.sort_values("data")
    artefato = {
        "modelo": final,
        "lista_ubs": lista_ubs,
        "historico": {chave: list(zip(g["data"], g["procura"].astype(int).tolist(), strict=True))
                      for chave, g in ordenada.groupby(["ubs", "turno"])},
        "clima": {linha["data"]: {c: float(linha[c]) for c in CLIMA} for linha in dim_data.to_dict("records")},
        "normais": {int(mes): {c: float(v) for c, v in linha.items()}
                    for mes, linha in dim_data.groupby("mes")[CLIMA].mean().round(1).to_dict("index").items()},
        "feriados": feriados,
        "metricas": metricas,
    }
    caminho_modelo.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(artefato, caminho_modelo, compress=3)
    (caminho_modelo.parent / "metricas.json").write_text(json.dumps(metricas, indent=2, ensure_ascii=False) + "\n")
    return metricas


def main() -> None:
    m = treinar()
    print(f"modelo escolhido na validação: {m['modelo']} {m['mae_validacao_por_candidato']}")
    print(f"teste: {m['periodo_teste'][0]} a {m['periodo_teste'][1]} ({m['linhas_teste']} linhas)")
    print(f"{'turno':<7}{'MAE':>7}{'média':>8}{'% média':>9}{'meta <15%':>11}{'base MAE':>10}")
    for turno, r in m["teste"]["por_turno"].items():
        base = m["linha_de_base_media_movel_7d"]["por_turno"][turno]["mae"]
        print(f"{turno:<7}{r['mae']:>7.2f}{r['media']:>8.1f}{r['pct_da_media']:>8.1f}%"
              f"{'sim' if r['meta_ok'] else 'não':>11}{base:>10.2f}")
    print(f"MAE geral: {m['teste']['mae_geral']} | linha de base (média móvel 7d): "
          f"{m['linha_de_base_media_movel_7d']['mae_geral']}")


if __name__ == "__main__":
    main()
