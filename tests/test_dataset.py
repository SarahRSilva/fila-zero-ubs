from datetime import date

import pytest
from gerar_dataset import FERIADOS, gerar


@pytest.fixture(scope="module")
def dados():
    return gerar(date(2026, 3, 1), date(2026, 4, 30), seed=7)


def test_colunas_do_bronze(dados):
    atend, _, _ = dados
    assert list(atend.columns) == [
        "id", "cpf_hash", "ubs", "data", "turno", "hora_chegada",
        "hora_atendimento", "espera_min", "motivo", "cor_triagem", "atendido",
    ]
    assert atend["id"].is_unique


def test_espera_nunca_negativa(dados):
    atend, _, _ = dados
    atendidos = atend[atend["atendido"] == "S"]
    assert (atendidos["espera_min"].astype(int) >= 0).all()


def test_sem_atendimento_em_fim_de_semana_ou_feriado(dados):
    _, _, dem = dados
    dias = [date.fromisoformat(d) for d in dem["data"].unique()]
    assert all(d.weekday() < 5 and d not in FERIADOS for d in dias)


def test_segunda_tem_mais_procura_que_sexta(dados):
    _, _, dem = dados
    media = dem.groupby("dia_semana")["procura"].mean()
    assert media[0] > media[4]


def test_mesma_semente_mesmo_resultado():
    a, _, _ = gerar(date(2026, 3, 2), date(2026, 3, 6), seed=1)
    b, _, _ = gerar(date(2026, 3, 2), date(2026, 3, 6), seed=1)
    assert a.equals(b)
