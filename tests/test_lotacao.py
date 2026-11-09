"""Leituras do sensor no lake: geração sintética, coletor e fato_lotacao."""
import json
import sys
import time
from datetime import date
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pandas as pd
from gerar_dataset import gerar, gerar_lotacao, salvar

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "bigdata"))
sys.path.insert(0, str(RAIZ / "iot"))
import coletor  # noqa: E402
import pipeline  # noqa: E402


def test_sala_enche_de_manha_e_esvazia(tmp_path):
    atend, clima, dem = gerar(date(2026, 3, 2), date(2026, 3, 6), seed=5)
    lot = gerar_lotacao(atend, clima, np.random.default_rng(1))
    lot["h"] = lot["ts"].str[11:13].astype(int)
    media = lot.groupby("h")["ocupacao"].mean()
    assert media[7] > media[11] and media[7] > media[20]
    assert (lot["ocupacao"] >= 0).all() and set(lot["alerta"]) <= {"S", "N"}


def test_t06_mensagem_mqtt_chega_ao_fato_lotacao_em_ate_5s(tmp_path, monkeypatch):
    atend, clima, dem = gerar(date(2026, 3, 2), date(2026, 3, 6), seed=5)
    salvar(atend, clima, dem, raiz=tmp_path)
    lake = tmp_path / "bigdata" / "lake"
    gravar_original = coletor.gravar
    monkeypatch.setattr(coletor, "gravar", lambda corpo: gravar_original(corpo, lake / "bronze"))
    corpo = {"ubs": "UBS Vila Nova", "ocupacao": 13, "capacidade": 20, "temperatura": 25.0, "origem": "mock",
             "ts": "2026-03-04T12:00:00Z"}

    inicio = time.perf_counter()
    coletor.ao_receber(None, None, SimpleNamespace(topic="filazero/ubs/vila-nova/sala", payload=json.dumps(corpo)))
    pipeline.rodar(lake)
    fato = pd.read_parquet(lake / "gold" / "fato_lotacao.parquet")
    assert time.perf_counter() - inicio < 5
    assert (fato["ocupacao"] == 13).any()


def test_coletor_grava_bronze_e_pipeline_gera_fato_lotacao(tmp_path):
    atend, clima, dem = gerar(date(2026, 3, 2), date(2026, 3, 6), seed=5)
    salvar(atend, clima, dem, raiz=tmp_path)
    bronze = tmp_path / "bigdata" / "lake" / "bronze"
    coletor.gravar({"ubs": "UBS Vila Nova", "ocupacao": 19, "capacidade": 20, "temperatura": 26.1,
                    "alerta": True, "origem": "esp32", "ts": "2026-03-03T10:00:00Z"}, bronze)
    coletor.gravar({"ubs": "UBS Vila Nova", "ocupacao": -1, "capacidade": 20, "ts": "2026-03-03T10:10:00Z"}, bronze)
    coletor.gravar({"ubs": "UBS Vila Nova", "ocupacao": 5, "capacidade": 20, "ts": "quando?"}, bronze)

    pipeline.rodar(tmp_path / "bigdata" / "lake")
    fato = pd.read_parquet(tmp_path / "bigdata" / "lake" / "gold" / "fato_lotacao.parquet")
    assert len(fato) == 1
    linha = fato.iloc[0]
    assert linha["hora"] == 7 and linha["nome_dia"] == "terca" and bool(linha["alerta"])  # 10h UTC = 7h em SP
    rej = pd.read_csv(tmp_path / "bigdata" / "lake" / "rejeitados" / "lotacao_rejeitadas.csv")
    assert sorted(rej["motivo_rejeicao"]) == ["ocupacao invalida", "ts invalido"]
