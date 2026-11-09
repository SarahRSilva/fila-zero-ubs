"""Agente de pré-triagem com LLM (Claude), executando o prompt ia/prompts/triagem_v1.md.

Só é chamado quando ANTHROPIC_API_KEY está definida. Sem chave, ou em qualquer falha
da chamada, vale a classificação por regras. As regras também são o piso de segurança:
o modelo pode subir a cor, nunca baixar.

Atenção: com a chave definida, o relato do cidadão sai para um serviço externo.
"""
from __future__ import annotations

import json
import logging
import os
from pathlib import Path

from ia.triagem import Triagem, classificar, resumo

log = logging.getLogger("filazero.triagem")
PROMPT = Path(__file__).resolve().parent / "prompts" / "triagem_v1.md"
MODELO = os.getenv("LLM_MODELO", "claude-opus-5-5")
GRAVIDADE = {"verde": 0, "amarelo": 1, "vermelho": 2}
ESQUEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["cor", "motivo_resumido", "turno_sugerido", "orientacao", "pergunta"],
    "properties": {
        "cor": {"type": "string", "enum": ["verde", "amarelo", "vermelho"]},
        "motivo_resumido": {"type": "string"},
        "turno_sugerido": {"type": "string", "enum": ["manha", "tarde", "agora"]},
        "orientacao": {"type": "string"},
        "pergunta": {"anyOf": [{"type": "string"}, {"type": "null"}]},
    },
}


def _perguntar_ao_modelo(relato: str, resposta_anterior: str | None) -> dict | None:
    import anthropic  # só é necessário com o agente ligado

    conteudo = f"Relato do cidadão:\n{relato}"
    if resposta_anterior:
        conteudo += f"\n\nResposta do cidadão à pergunta de esclarecimento:\n{resposta_anterior}"
    cliente = anthropic.Anthropic(timeout=20.0, max_retries=1)
    mensagem = cliente.beta.messages.create(
        model=MODELO, max_tokens=2000, system=PROMPT.read_text(encoding="utf-8"),
        betas=["server-side-fallback-2026-07-01"], fallbacks="default",
        output_config={"effort": "low", "format": {"type": "json_schema", "schema": ESQUEMA}},
        messages=[{"role": "user", "content": conteudo}],
    )
    if mensagem.stop_reason != "end_turn":
        log.warning("triagem LLM terminou com stop_reason=%s", mensagem.stop_reason)
        return None
    return json.loads(next(b.text for b in mensagem.content if b.type == "text"))


def classificar_com_llm(relato: str, resposta_anterior: str | None = None) -> Triagem:
    regras = classificar(relato, resposta_anterior)
    if not os.getenv("ANTHROPIC_API_KEY"):
        return regras
    try:
        dados = _perguntar_ao_modelo(relato, resposta_anterior)
    except Exception as erro:  # a triagem não pode cair junto com um serviço externo
        log.warning("triagem LLM indisponível, usando regras: %s", type(erro).__name__)
        return regras
    if dados is None or GRAVIDADE[dados["cor"]] < GRAVIDADE[regras.cor]:
        return regras
    agora = dados["cor"] == "vermelho"
    turno = dados["turno_sugerido"]
    return Triagem(
        cor=dados["cor"], motivo_resumido=resumo(dados["motivo_resumido"] or relato),
        turno_sugerido="agora" if agora else ("tarde" if turno == "agora" else turno),
        orientacao=regras.orientacao if regras.cor == "vermelho" else dados["orientacao"],
        pergunta=None if agora or resposta_anterior else dados["pergunta"],
    )
