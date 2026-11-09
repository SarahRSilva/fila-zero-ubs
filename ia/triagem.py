"""Pré-triagem por regras: mesmo contrato de saída do prompt em ia/prompts/triagem_v1.md.

É a versão que roda sem chave de API e, quando o agente com LLM está ligado
(ia/triagem_llm.py), a verificação de segurança sobre a resposta dele: sinal de
emergência nunca pode sair rebaixado.

Os termos são expressões regulares aplicadas ao texto sem acento e em minúsculas.
Todos começam em início de palavra, para "pus" não casar com "campus".
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import asdict, dataclass

CRISE = [
    r"quero (me )?(matar|morrer)", r"me matar", r"suicid", r"tirar (a )?minha (propria )?vida",
    r"acabar com (a )?minha vida", r"acabar com tudo", r"nao quero (mais )?viver", r"automutil", r"me cortar",
    r"sumir do mundo",
]
VERMELHO = [
    r"(dor|dores|apert\w*) (\w+ ){0,2}no peito", r"apert\w* o peito", r"falta de ar", r"sem ar\b", r"puxar o ar",
    r"nao acorda", r"nao responde", r"de [1-3] mes(es)?\b.*febre", r"vomit\w* sangue", r"tossi\w* sangue",
    r"sangue (no|na|nas) (vomito|fezes)", r"sangue nao para", r"nao para de sangrar", r"jorr", r"entort",
    r"(braco|perna) (\w+ )?mole", r"nao consig\w* respirar", r"parou de respirar",
    r"nao (esta |estou )?respira", r"dificuldade (para|pra|de|em) respirar", r"respirar com dificuldade", r"sufoc",
    r"sangramento que nao para", r"sangrando muito", r"hemorragia", r"desmai", r"perd\w+ a consciencia",
    r"desacordad", r"inconsciente", r"confus", r"convuls", r"manchas? (\w+ )?na pele", r"sangramento na gengiva",
    r"gengiva sangrando", r"febre (alta )?(em|no|na) (bebe|recem)", r"bebe (\w+ ){0,3}febre", r"labios? rox",
    r"fraqueza (de|em|num|no) (um )?lado", r"boca torta", r"infart", r"ataque cardiaco", r"parada cardiaca",
    r"avc\b", r"derrame", r"envenen", r"overdose", r"anafil",
]
AMARELO = [
    r"febre", r"(39|4[0-2])( ?graus| ?°)", r"dor (\w+ ){0,3}(forte|intensa|insuportavel)", r"muita dor",
    r"ferida (infeccionada|infectada)", r"pus\b", r"vomit", r"diarreia", r"tosse (ha|faz|forte|persistente|com)",
    r"dengue", r"dor de ouvido", r"queimadura", r"queimei", r"machuc", r"inflam", r"dor ao urinar", r"ardencia",
    r"pressao subiu",
    r"(?<!da )(?<!de )(?<!para )pressao (muito |bem )?alta", r"(?<!da )(?<!de )(?<!para )glicemia alta",
    r"(febre|dor|tosse|vomit\w*|enjoo|tontura|mal estar)\b.*\b([3-9]|tres|quatro|cinco|seis|sete|varios|muitos) dias",
]
VERDE = [
    r"receita", r"renov", r"vacina", r"exame", r"resultado", r"acompanhamento", r"pre.?natal", r"pressao", r"diabetes",
    r"curativo", r"puericultura", r"rotina", r"atestado", r"encaminhamento", r"pesar", r"gestante", r"preventivo",
]
# Toda pergunta é feita de modo que "sim" seja o sinal de alerta: o chat responde com botões Sim e Não.
PERGUNTAS_AMARELO = {
    r"febre": "A febre passa de 39 °C, ou você notou manchas na pele ou sangramento na gengiva?",
    r"dor": "A dor é no peito ou veio junto com falta de ar?",
    r"vomit": "Você está sem conseguir beber água ou urinando bem menos que o normal?",
    r"diarreia": "Você está sem conseguir beber água ou urinando bem menos que o normal?",
    r"tosse": "Está com falta de ar ou os lábios ficaram roxos?",
}
ORIENTA_EMERGENCIA = "Esses são sinais de emergência. Não espere a UBS: procure a UPA mais próxima agora ou ligue 192."
ORIENTA_CRISE = ("Sinto muito que você esteja passando por isso. Você não precisa enfrentar isso sozinho: "
                 "ligue agora para o CVV, 188, 24 horas e gratuito. Se houver risco imediato, ligue 192 ou vá à UPA.")
ORIENTA_AMARELO = "Isso precisa de atendimento o quanto antes. Vou sugerir o turno com menos espera."
ORIENTA_DESCONHECIDO = ("Não consegui avaliar seu relato com segurança, então a equipe da UBS precisa ver você "
                        "o quanto antes. Se piorar ou parecer grave, não espere: ligue 192.")


@dataclass
class Triagem:
    cor: str
    motivo_resumido: str
    turno_sugerido: str
    orientacao: str
    pergunta: str | None = None

    def dict(self) -> dict:
        return asdict(self)


def normalizar(texto: str) -> str:
    texto = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode().lower()
    return re.sub(r"\s+", " ", texto).strip()


def resumo(texto: str) -> str:
    limpo = re.sub(r"\s+", " ", texto.strip())
    return limpo[:77] + "..." if len(limpo) > 80 else limpo


def _tem(termos: list[str], texto: str) -> bool:
    return any(re.search(r"\b" + termo if termo[0] not in "(" else termo, texto) for termo in termos)


def _negou(resposta: str) -> bool:
    return bool(re.match(r"(nao|n)\b", resposta))


def _afirmou(resposta: str) -> bool:
    return not _negou(resposta) and bool(re.search(r"\b(sim|s|tenho|tem|estou|isso|aham|uhum|claro)\b", resposta))


def _pergunta_amarelo(texto: str) -> str | None:
    return next((q for chave, q in PERGUNTAS_AMARELO.items() if re.search(r"\b" + chave, texto)), None)


def classificar(relato: str, resposta_anterior: str | None = None) -> Triagem:
    """Classifica o relato do cidadão. `resposta_anterior` é a resposta à pergunta
    de esclarecimento, quando houver."""
    t = normalizar(relato)
    r = normalizar(resposta_anterior or "")
    alvo = t if _negou(r) else f"{t} {r}".strip()  # "não, sem falta de ar" não é sinal de alerta
    motivo = resumo(relato)

    if _tem(CRISE, alvo):
        return Triagem("vermelho", motivo, "agora", ORIENTA_CRISE)
    if _tem(VERMELHO, alvo):
        return Triagem("vermelho", motivo, "agora", ORIENTA_EMERGENCIA)

    if _tem(AMARELO, alvo):
        pergunta = _pergunta_amarelo(t)
        if r and pergunta and _afirmou(r):
            return Triagem("vermelho", motivo, "agora", ORIENTA_EMERGENCIA)
        return Triagem("amarelo", motivo, "tarde", ORIENTA_AMARELO, None if r else pergunta)

    if _tem(VERDE, alvo):
        return Triagem("verde", motivo, "manha",
                       "É um atendimento de rotina: dá para escolher o turno mais tranquilo, sem pressa.")

    if len(t) < 12:
        return Triagem("verde", motivo, "manha", "",
                       "Me conta um pouco mais: o que você está sentindo e desde quando?")

    # Relato que as regras não reconhecem nunca sai verde: verde exige evidência de rotina.
    return Triagem("amarelo", motivo, "tarde", ORIENTA_DESCONHECIDO,
                   None if r else "Tem febre, dor forte ou alguma coisa começou de repente?")
