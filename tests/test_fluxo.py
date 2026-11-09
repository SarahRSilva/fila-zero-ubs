"""T08 (fluxo do cidadão até o painel), cadastro, limites de acesso e regras do atendimento."""
from datetime import date, timedelta

JARDIM, VILA = "UBS Jardim Esperanca", "UBS Vila Nova"
DIA = "2030-03-19"  # terça-feira futura


def novo_cidadao(cliente, email):
    r = cliente.post("/cadastro", json={"nome": "Pessoa Teste", "email": email, "senha": "senha-boa-123"})
    assert r.status_code == 201, r.text
    assert r.json()["perfil"] == "cidadao"
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def corpo(**extra):
    return {"ubs": JARDIM, "data": DIA, "turno": "tarde", "motivo": "febre há 3 dias", "cor_triagem": "amarelo",
            **extra}


def test_t08_fluxo_do_chat_ao_painel_e_troca_de_turno(cliente, gestora):
    cid = novo_cidadao(cliente, "t08@teste.dev")
    triagem = cliente.post("/triagem", json={"relato": "estou com febre há 3 dias e dor de cabeça"}, headers=cid).json()
    assert triagem["cor"] == "amarelo" and triagem["pergunta"]
    final = cliente.post("/triagem", json={"relato": "estou com febre há 3 dias e dor de cabeça",
                                           "resposta_anterior": "Não, nada disso"}, headers=cid).json()
    assert final["cor"] == "amarelo" and final["pergunta"] is None
    assert cliente.get("/previsao", params={"data": DIA}, headers=cid).json()["aberta"] is True

    registro = cliente.post("/atendimento", json=corpo(), headers=cid).json()
    painel = cliente.get("/atendimento", params={"data": DIA}, headers=gestora).json()
    assert registro["id"] in {a["id"] for a in painel}

    trocado = cliente.post("/atendimento", json=corpo(turno="noite"), headers=cid)
    assert trocado.status_code == 201 and trocado.json()["id"] == registro["id"]
    meus = cliente.get("/atendimento", params={"data": DIA}, headers=cid).json()
    assert len(meus) == 1 and meus[0]["turno"] == "noite"


def test_cadastro_recusa_duplicado_senha_curta_e_perfil_extra(cliente):
    novo_cidadao(cliente, "duplicado@teste.dev")
    dados = {"nome": "Outra", "email": "DUPLICADO@teste.dev", "senha": "senha-boa-123"}
    assert cliente.post("/cadastro", json=dados).status_code == 409
    assert cliente.post("/cadastro", json={**dados, "email": "a@b.dev", "senha": "curta"}).status_code == 422
    assert cliente.post("/cadastro", json={**dados, "email": "a@b.dev", "perfil": "gestora"}).status_code == 422


def test_gestora_fica_restrita_a_propria_unidade(cliente, gestora):
    assert cliente.get("/atendimento", params={"ubs": VILA}, headers=gestora).status_code == 403
    assert cliente.post("/atendimento", json=corpo(ubs=VILA), headers=gestora).status_code == 403
    leitura = {"ubs": VILA, "ocupacao": 5, "capacidade": 20}
    assert cliente.post("/sala", json=leitura, headers=gestora).status_code == 403


def test_gestora_nao_recebe_atendimento_de_outra_unidade(cliente, gestora):
    cid = novo_cidadao(cliente, "vila@teste.dev")
    assert cliente.post("/atendimento", json=corpo(ubs=VILA), headers=cid).status_code == 201
    assert {a["ubs"] for a in cliente.get("/atendimento", headers=gestora).json()} == {JARDIM}


def test_nao_registra_em_dia_fechado_nem_em_data_passada(cliente, cidadao):
    r = cliente.post("/atendimento", json=corpo(data="2026-11-20"), headers=cidadao)
    assert r.status_code == 422 and "feriado" in r.json()["detail"]
    assert cliente.post("/atendimento", json=corpo(data="2030-03-16"), headers=cidadao).status_code == 422  # sábado
    ontem = date.today() - timedelta(days=2)
    while ontem.weekday() > 4:
        ontem -= timedelta(days=1)
    assert cliente.post("/atendimento", json=corpo(data=ontem.isoformat()), headers=cidadao).status_code == 422


def test_login_bloqueia_depois_de_muitas_falhas(cliente):
    novo_cidadao(cliente, "alvo@teste.dev")
    dados = {"email": "alvo@teste.dev", "senha": "errada"}
    for _ in range(10):
        assert cliente.post("/login", json=dados).status_code == 401
    bloqueado = cliente.post("/login", json=dados)
    assert bloqueado.status_code == 429 and "Retry-After" in bloqueado.headers
    assert cliente.post("/login", json={**dados, "senha": "senha-boa-123"}).status_code == 429
