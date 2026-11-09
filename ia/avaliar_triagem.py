"""Mede a triagem contra dois gabaritos de 30 relatos (10 por cor).

Uso:
    python ia/avaliar_triagem.py         # regras; grava ia/modelo/metricas_triagem.json
    python ia/avaliar_triagem.py --llm   # agente com LLM (exige ANTHROPIC_API_KEY e gera custo);
                                         # grava ia/modelo/metricas_triagem_llm.json

ajuste     relatos usados para corrigir as regras; a nota não é independente
validacao  relatos separados para medir; depois de lidos, novos ajustes invalidam a nota
O erro que importa é vermelho classificado como verde.
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from collections.abc import Callable
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

from ia.triagem import classificar  # noqa: E402

GABARITO = RAIZ / "ia" / "avaliacao" / "gabarito_triagem.csv"
VALIDACAO = RAIZ / "ia" / "avaliacao" / "validacao_triagem.csv"
SAIDA = RAIZ / "ia" / "modelo" / "metricas_triagem.json"
CORES = ["vermelho", "amarelo", "verde"]


def avaliar(gabarito: Path = GABARITO, classificador: Callable = classificar) -> dict:
    with gabarito.open(encoding="utf-8", newline="") as f:
        casos = list(csv.DictReader(f))
    matriz = {real: {previsto: 0 for previsto in CORES} for real in CORES}
    erros = []
    for caso in casos:
        previsto = classificador(caso["relato"]).cor
        matriz[caso["cor_esperada"]][previsto] += 1
        if previsto != caso["cor_esperada"]:
            erros.append({"relato": caso["relato"], "esperado": caso["cor_esperada"], "previsto": previsto})
    acertos = sum(matriz[c][c] for c in CORES)
    return {
        "casos": len(casos), "acertos": acertos, "acuracia": round(acertos / len(casos), 3),
        "vermelho_detectado": matriz["vermelho"]["vermelho"], "vermelho_como_verde": matriz["vermelho"]["verde"],
        "matriz_real_x_previsto": matriz, "erros": erros,
    }


def imprimir(nome: str, r: dict) -> None:
    print(f"{nome}: {r['acertos']}/{r['casos']} = {r['acuracia']:.1%} | "
          f"vermelho detectado: {r['vermelho_detectado']}/10 | vermelho como verde: {r['vermelho_como_verde']}")
    print(f"{'real / previsto':<17}" + "".join(f"{c:>10}" for c in CORES))
    for real in CORES:
        print(f"{real:<17}" + "".join(f"{r['matriz_real_x_previsto'][real][p]:>10}" for p in CORES))
    for e in r["erros"]:
        print(f"  [{e['esperado']} -> {e['previsto']}] {e['relato']}")


def main() -> None:
    ap = argparse.ArgumentParser(description="Acurácia e matriz de confusão da triagem")
    ap.add_argument("--llm", action="store_true", help="mede o agente com LLM em vez das regras")
    args = ap.parse_args()
    classificador, saida = classificar, SAIDA
    if args.llm:
        from ia.triagem_llm import classificar_com_llm
        classificador, saida = classificar_com_llm, SAIDA.with_name("metricas_triagem_llm.json")
    resultado = {"ajuste": avaliar(GABARITO, classificador), "validacao": avaliar(VALIDACAO, classificador)}
    saida.write_text(json.dumps(resultado, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    imprimir("ajuste", resultado["ajuste"])
    imprimir("validacao", resultado["validacao"])


if __name__ == "__main__":
    main()
