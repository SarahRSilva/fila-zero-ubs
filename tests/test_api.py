"""Login, atendimento e previsão pela API. T04 e T05 do plano de testes."""
import jwt

ATENDIMENTO = {
    "ubs": "UBS Jardim Esperanca", "data": "2030-03-18", "turno": "tarde",  # segunda-feira futura
    "motivo": "febre ha 3 dias", "cor_triagem": "amarelo",
}


def test_login_devolve_token_com_perfil(cliente):
    r = cliente.post("/login", json={"email": "gestora@filazero.dev", "senha": "senha-de-teste"})
    assert r.status_code == 200
    corpo = r.json()
    assert corpo["perfil"] == "gestora" and corpo["ubs"] == "UBS Jardim Esperanca"
    assert jwt.decode(corpo["access_token"], options={"verify_signature": False})["perfil"] == "gestora"


def test_login_com_senha_errada_ou_usuario_inexistente_da_401(cliente):
    for email in ("gestora@filazero.dev", "ninguem@filazero.dev"):
        r = cliente.post("/login", json={"email": email, "senha": "errada"})
        assert r.status_code == 401
        assert r.json()["detail"] == "E-mail ou senha incorretos"


def test_t04_atendimento_sem_token_da_401(cliente):
    assert cliente.post("/atendimento", json=ATENDIMENTO).status_code == 401
    assert cliente.get("/atendimento").status_code == 401
    assert cliente.get("/previsao", params={"data": "2026-11-23"}).status_code == 401


def test_token_adulterado_da_401(cliente, cidadao):
    adulterado = {"Authorization": cidadao["Authorization"][:-3] + "abc"}
    assert cliente.post("/atendimento", json=ATENDIMENTO, headers=adulterado).status_code == 401


def test_t05_espera_negativa_da_422_com_mensagem(cliente, cidadao):
    r = cliente.post("/atendimento", json={**ATENDIMENTO, "espera_min": -5}, headers=cidadao)
    assert r.status_code == 422
    erro = r.json()["detail"][0]
    assert erro["loc"] == ["body", "espera_min"]
    assert "greater than or equal to 0" in erro["msg"]


def test_entrada_invalida_da_422(cliente, cidadao):
    invalidos = [
        {**ATENDIMENTO, "turno": "madrugada"},
        {**ATENDIMENTO, "cor_triagem": "roxo"},
        {**ATENDIMENTO, "ubs": "UBS Inexistente"},
        {**ATENDIMENTO, "hora_chegada": "10:00", "hora_atendimento": "09:00"},
        {**ATENDIMENTO, "atendido": True},
        {**ATENDIMENTO, "campo_extra": 1},
    ]
    for corpo in invalidos:
        assert cliente.post("/atendimento", json=corpo, headers=cidadao).status_code == 422, corpo


def test_cidadao_registra_e_so_ve_o_proprio_atendimento(cliente, cidadao, gestora):
    criado = cliente.post("/atendimento", json=ATENDIMENTO, headers=cidadao)
    assert criado.status_code == 201
    corpo = criado.json()
    assert corpo["atendido"] is False and len(corpo["cidadao_hash"]) == 16

    cliente.post("/atendimento", json={**ATENDIMENTO, "motivo": "vacina", "cor_triagem": "verde"}, headers=gestora)

    do_cidadao = cliente.get("/atendimento", headers=cidadao).json()
    assert {a["cidadao_hash"] for a in do_cidadao} == {corpo["cidadao_hash"]}
    da_gestora = cliente.get("/atendimento", params={"data": ATENDIMENTO["data"]}, headers=gestora).json()
    assert len({a["cidadao_hash"] for a in da_gestora}) == 2


def test_previsao_devolve_os_tres_turnos(cliente, gestora):
    r = cliente.get("/previsao", params={"data": "2026-11-23"}, headers=gestora)
    assert r.status_code == 200
    corpo = r.json()
    assert corpo["aberta"] is True and corpo["ubs"] == "UBS Jardim Esperanca"
    assert set(corpo["turnos"]) == {"manha", "tarde", "noite"}
    assert all(isinstance(v, int) and v > 0 for v in corpo["turnos"].values())


def test_previsao_em_feriado_avisa_que_a_ubs_fecha(cliente, gestora):
    corpo = cliente.get("/previsao", params={"data": "2026-11-20"}, headers=gestora).json()
    assert corpo["aberta"] is False and corpo["motivo_fechada"] == "feriado"
    assert corpo["turnos"] == {"manha": 0, "tarde": 0, "noite": 0}


def test_previsao_com_entrada_invalida_da_422(cliente, gestora):
    assert cliente.get("/previsao", params={"data": "amanha"}, headers=gestora).status_code == 422
    r = cliente.get("/previsao", params={"data": "2026-11-23", "ubs": "UBS Inexistente"}, headers=gestora)
    assert r.status_code == 422
