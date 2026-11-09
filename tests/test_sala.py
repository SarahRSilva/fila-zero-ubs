"""Sensor da sala: leitura entra (MQTT ou HTTP) e sai em GET /sala/agora."""
from app import mqtt


def test_sem_leitura_da_404(cliente, gestora):
    assert cliente.get("/sala/agora", params={"ubs": "UBS Vila Nova"}, headers=gestora).status_code == 404


def test_leitura_mqtt_aparece_em_sala_agora(cliente, gestora):
    mqtt.registrar_leitura({"ubs": "UBS Jardim Esperanca", "ocupacao": 28, "capacidade": 30, "temperatura": 27.5,
                            "origem": "mock"}, "filazero/ubs/jardim-esperanca/sala")
    r = cliente.get("/sala/agora", headers=gestora)
    assert r.status_code == 200
    corpo = r.json()
    assert corpo["ocupacao"] == 28 and corpo["alerta"] is True and corpo["taxa_ocupacao"] == 0.933
    assert corpo["segundos_atras"] < 5 and corpo["alertas_hoje"] >= 1


def test_leitura_por_http_so_gestora(cliente, gestora, cidadao):
    corpo = {"ubs": "UBS Jardim Esperanca", "ocupacao": 10, "capacidade": 30, "origem": "teste"}
    assert cliente.post("/sala", json=corpo, headers=cidadao).status_code == 403
    r = cliente.post("/sala", json=corpo, headers=gestora)
    assert r.status_code == 201 and r.json()["alerta"] is False
    assert cliente.post("/sala", json={**corpo, "capacidade": 0}, headers=gestora).status_code == 422
    assert cliente.post("/sala", json={**corpo, "ubs": "UBS X"}, headers=gestora).status_code == 422


def test_leitura_invalida_e_recusada():
    import pytest
    with pytest.raises(ValueError):
        mqtt.registrar_leitura({"ubs": "", "ocupacao": 1, "capacidade": 30})
    with pytest.raises(KeyError):
        mqtt.registrar_leitura({"ubs": "UBS Vila Nova"})
