"""T07: o pipeline roda sobre um bronze com 2 linhas inválidas."""
import sys
from datetime import date
from pathlib import Path

import pandas as pd
import pytest
from gerar_dataset import gerar, salvar

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "bigdata"))
import pipeline  # noqa: E402


@pytest.fixture()
def lake(tmp_path):
    atend, clima, dem = gerar(date(2026, 3, 2), date(2026, 3, 13), seed=3)
    salvar(atend, clima, dem, raiz=tmp_path)
    return tmp_path / "bigdata" / "lake"


def test_t07_duas_linhas_invalidas_vao_para_rejeitados_com_motivo(lake):
    arquivo = lake / "bronze" / "atendimentos_2026-03.csv"
    bronze = pd.read_csv(arquivo, dtype=str, keep_default_na=False)
    validas = len(bronze)
    sem_data = {**bronze.iloc[0], "id": "900001", "data": ""}
    espera_negativa = {**bronze.iloc[0], "id": "900002", "espera_min": "-12"}
    pd.concat([bronze, pd.DataFrame([sem_data, espera_negativa])]).to_csv(arquivo, index=False)

    resumo = pipeline.rodar(lake)

    assert resumo == {"lidas": validas + 2, "validas": validas, "rejeitadas": 2}
    rejeitados = pd.read_csv(lake / "rejeitados" / "atendimentos_rejeitados.csv", dtype=str, keep_default_na=False)
    assert dict(zip(rejeitados["id"], rejeitados["motivo_rejeicao"], strict=True)) == {
        "900001": "sem data", "900002": "espera negativa"}
    for tabela in ("fato_atendimento", "dim_data", "dim_turno", "dim_ubs"):
        assert (lake / "gold" / f"{tabela}.parquet").exists()
    assert len(pd.read_parquet(lake / "gold" / "fato_atendimento.parquet")) == validas


def test_gold_tem_calendario_e_cores_padronizadas(lake):
    arquivo = lake / "bronze" / "atendimentos_2026-03.csv"
    bronze = pd.read_csv(arquivo, dtype=str, keep_default_na=False)
    bronze.loc[0, "cor_triagem"] = " VERMELHO "
    bronze.loc[1, "turno"] = ""  # turno ausente é derivado da hora de chegada
    bronze.to_csv(arquivo, index=False)

    assert pipeline.rodar(lake)["rejeitadas"] == 0
    fato = pd.read_parquet(lake / "gold" / "fato_atendimento.parquet")
    assert set(fato["cor_triagem"]) <= {"verde", "amarelo", "vermelho"}
    assert fato.loc[fato["id"] == int(bronze.loc[1, "id"]), "turno"].item() == "manha"
    assert (fato.loc[fato["atendido"], "espera_min"] >= 0).all()

    dim = pd.read_parquet(lake / "gold" / "dim_data.parquet")
    assert len(dim) == 12 and dim["data"].is_unique
    assert dim.loc[dim["data"] == date(2026, 3, 2), "nome_dia"].item() == "segunda"


def test_bronze_vazio_falha_com_mensagem_clara(tmp_path):
    (tmp_path / "bronze").mkdir()
    with pytest.raises(FileNotFoundError, match="gerar_dataset"):
        pipeline.rodar(tmp_path)
