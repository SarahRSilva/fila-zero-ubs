"""O dashboard abre sobre o gold e responde aos filtros sem erro."""
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

RAIZ = Path(__file__).resolve().parents[1]
GOLD = RAIZ / "bigdata" / "lake" / "gold"

pytestmark = pytest.mark.skipif(not (GOLD / "fato_atendimento.parquet").exists(),
                                reason="gold ausente: rode data/gerar_dataset.py e bigdata/pipeline.py")


def numero(app: AppTest, rotulo: str) -> str:
    return next(m.value for m in app.metric if m.label == rotulo)


def test_dashboard_abre_e_filtra():
    app = AppTest.from_file(str(RAIZ / "bigdata" / "dashboard" / "app.py"), default_timeout=60).run()
    assert not app.exception
    total = numero(app, "Idas à UBS")

    app.multiselect[0].select("UBS Vila Nova").run()   # UBS
    app.multiselect[3].select("noite").run()           # turno
    assert not app.exception
    assert numero(app, "Idas à UBS") != total

    app.multiselect[1].select("2026-03").run()         # mês fora do período de teste do modelo
    assert not app.exception
    assert any("período de teste" in w.value for w in app.warning)
