"""Pré-triagem por regras: sinal de emergência nunca sai rebaixado."""
import pytest
from ia.triagem import classificar


@pytest.mark.parametrize("relato", [
    "estou com dor no peito", "Meu filho está com falta de ar", "sangramento que não para",
    "FEBRE e manchas na pele", "bebê com febre alta",
])
def test_sinal_de_emergencia_e_vermelho(relato):
    t = classificar(relato)
    assert t.cor == "vermelho" and t.turno_sugerido == "agora" and "192" in t.orientacao


def test_febre_ha_tres_dias_e_amarelo_com_pergunta():
    t = classificar("Estou com febre há 3 dias e dor no corpo.")
    assert t.cor == "amarelo" and t.pergunta and "39" in t.pergunta


def test_resposta_sim_a_pergunta_vira_vermelho():
    assert classificar("febre há 3 dias", "sim").cor == "vermelho"
    assert classificar("febre há 3 dias", "não, nada disso").cor == "amarelo"


@pytest.mark.parametrize("relato", [
    "estou tendo um infarto", "acho que é um AVC", "dificuldade para respirar", "meu bebê parou de respirar",
])
def test_emergencias_que_passavam_como_verde(relato):
    assert classificar(relato).cor == "vermelho"


def test_crise_suicida_orienta_cvv():
    t = classificar("quero me matar")
    assert t.cor == "vermelho" and "188" in t.orientacao and "192" in t.orientacao


def test_febre_muito_alta_nao_sai_verde():
    assert classificar("febre de 40 graus").cor == "amarelo"


def test_sim_sobre_beber_agua_e_sinal_de_alerta_e_nao_o_contrario():
    t = classificar("estou vomitando desde ontem")
    assert "sem conseguir" in t.pergunta
    assert classificar("estou vomitando desde ontem", "Não, nada disso").cor == "amarelo"


def test_sim_na_pergunta_generica_nao_vira_emergencia():
    assert classificar("estou indisposta faz uma semana", "sim").cor == "amarelo"


def test_relato_desconhecido_nunca_sai_verde():
    assert classificar("estou indisposta faz uma semana").cor == "amarelo"
    assert classificar("estou indisposta faz uma semana", "não").cor == "amarelo"


def test_resposta_com_emergencia_sobe_mas_negacao_nao():
    assert classificar("febre há 3 dias", "agora estou com falta de ar").cor == "vermelho"
    assert classificar("febre há 3 dias", "não, sem falta de ar").cor == "amarelo"


@pytest.mark.parametrize("relato", ["preciso tomar a vacina no campus", "preciso renovar receita vencida há 3 dias",
                                    "receita do remédio da pressão alta"])
def test_palavra_solta_nao_muda_a_cor(relato):
    assert classificar(relato).cor == "verde"


def test_t03_relato_vazio_pergunta_em_vez_de_classificar():
    t = classificar("")
    assert t.pergunta and not t.orientacao


def test_gabarito_de_ajuste_sem_vermelho_como_verde():
    from ia.avaliar_triagem import avaliar
    r = avaliar()
    assert r["casos"] == 30 and r["vermelho_como_verde"] == 0


def _regras_e_llm(monkeypatch, resposta):
    import ia.triagem_llm as llm
    monkeypatch.setenv("ANTHROPIC_API_KEY", "chave-de-teste")
    monkeypatch.setattr(llm, "_perguntar_ao_modelo", resposta)
    return llm.classificar_com_llm


def test_llm_nao_rebaixa_emergencia(monkeypatch):
    f = _regras_e_llm(monkeypatch, lambda *_: {"cor": "verde", "motivo_resumido": "x", "turno_sugerido": "manha",
                                               "orientacao": "tranquilo", "pergunta": None})
    t = f("estou com dor no peito")
    assert t.cor == "vermelho" and "192" in t.orientacao


def test_llm_pode_subir_a_cor(monkeypatch):
    f = _regras_e_llm(monkeypatch, lambda *_: {"cor": "vermelho", "motivo_resumido": "desmaio",
                                               "turno_sugerido": "agora", "orientacao": "vá à UPA", "pergunta": None})
    t = f("preciso renovar a receita")
    assert t.cor == "vermelho" and t.turno_sugerido == "agora"


def test_falha_do_llm_cai_nas_regras(monkeypatch):
    def quebra(*_):
        raise RuntimeError("serviço fora")
    assert _regras_e_llm(monkeypatch, quebra)("tomar vacina da gripe").cor == "verde"


def test_sem_chave_nao_chama_llm(monkeypatch):
    import ia.triagem_llm as llm
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setattr(llm, "_perguntar_ao_modelo", lambda *_: pytest.fail("não devia chamar"))
    assert llm.classificar_com_llm("tomar vacina").cor == "verde"


def test_rotina_e_verde():
    for relato in ("renovar receita da pressão", "tomar vacina da gripe", "pegar resultado de exame"):
        t = classificar(relato)
        assert t.cor == "verde" and t.pergunta is None


def test_relato_curto_pede_mais_detalhes():
    assert classificar("oi").pergunta


def test_endpoint_exige_token_e_responde(cliente, cidadao):
    assert cliente.post("/triagem", json={"relato": "dor no peito"}).status_code == 401
    r = cliente.post("/triagem", json={"relato": "febre há 3 dias"}, headers=cidadao)
    assert r.status_code == 200 and r.json()["cor"] == "amarelo"
    assert cliente.post("/triagem", json={"relato": ""}, headers=cidadao).status_code == 422
