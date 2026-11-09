"""T01: o modelo de previsão recebe uma data válida e devolve três inteiros >= 0."""
from datetime import date

import pytest
from ia.previsao import TURNOS, Previsor


@pytest.fixture(scope="module")
def previsor():
    return Previsor.carregar()


@pytest.mark.parametrize("dia", [date(2026, 3, 9), date(2026, 10, 30), date(2026, 11, 23), date(2027, 2, 1)])
def test_t01_data_valida_devolve_tres_inteiros(previsor, dia):
    for ubs in previsor.lista_ubs:
        previsto = previsor.prever(dia, ubs)
        assert list(previsto) == TURNOS
        assert all(isinstance(v, int) and v >= 0 for v in previsto.values())


def test_segunda_de_abril_preve_mais_que_sexta_de_novembro(previsor):
    ubs = previsor.lista_ubs[0]
    assert sum(previsor.prever(date(2026, 4, 6), ubs).values()) > sum(previsor.prever(date(2026, 11, 27), ubs).values())


def test_dia_sem_expediente_devolve_zero(previsor):
    ubs = previsor.lista_ubs[0]
    assert previsor.motivo_fechada(date(2026, 11, 21)) == "fim de semana"
    assert previsor.motivo_fechada(date(2026, 11, 20)) == "feriado"
    assert previsor.prever(date(2026, 11, 21), ubs) == {"manha": 0, "tarde": 0, "noite": 0}


def test_ubs_desconhecida_e_recusada(previsor):
    with pytest.raises(ValueError):
        previsor.prever(date(2026, 11, 23), "UBS Inexistente")


def test_metricas_registradas_com_o_modelo(previsor):
    teste = previsor.metricas["teste"]
    assert teste["mae_geral"] > 0
    assert set(teste["por_turno"]) == set(TURNOS)
