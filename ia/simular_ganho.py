"""Simula 100 cidadãos num dia de pico: fila por ordem de chegada x distribuição por turno.

Uso (depois de bigdata/pipeline.py):
    python ia/simular_ganho.py

As chegadas do cenário "antes" são sorteadas do dia de maior procura do gold. Os dois
cenários usam a mesma equipe (4/3/2 profissionais) e os mesmos tempos de atendimento
(exponencial, média de 14 min). No "depois", uma parte das pessoas (adesão) segue o
turno sugerido e chega espalhada dentro dele; as demais mantêm o horário original.

É simulação sobre dados sintéticos: mostra o efeito do mecanismo, não um resultado medido em UBS real.
Saída: ia/modelo/ganho_simulado.json
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

RAIZ = Path(__file__).resolve().parents[1]
GOLD = RAIZ / "bigdata" / "lake" / "gold"
SAIDA = RAIZ / "ia" / "modelo" / "ganho_simulado.json"
PESSOAS, RODADAS, ATENDIMENTO_MIN = 100, 500, 14.0
TURNOS = [("manha", 7 * 60, 12 * 60, 4), ("tarde", 13 * 60, 17 * 60, 3), ("noite", 18 * 60, 21 * 60, 2)]
ADESOES = [1.0, 0.7, 0.5]


def simular_fila(chegadas: np.ndarray, atendimentos: np.ndarray) -> tuple[float, int]:
    """Fila única por ordem de chegada. Devolve (espera média em min de quem foi atendido, atendidos)."""
    profissionais = [[inicio, fim] for _, inicio, fim, n in TURNOS for _ in range(n)]
    esperas = []
    for i in np.argsort(chegadas, kind="stable"):
        chegada, duracao = chegadas[i], atendimentos[i]
        livres = [p for p in profissionais if max(chegada, p[0]) + duracao <= p[1]]
        if not livres:
            continue
        escolhido = min(livres, key=lambda p: max(chegada, p[0]))
        inicio = max(chegada, escolhido[0])
        escolhido[0] = inicio + duracao
        esperas.append(inicio - chegada)
    return float(np.mean(esperas)), len(esperas)


def chegadas_por_turno(n: int, rng: np.random.Generator) -> np.ndarray:
    """Divide as pessoas conforme a capacidade de cada turno e espalha as chegadas dentro dele."""
    capacidade = np.array([(fim - inicio) * k for _, inicio, fim, k in TURNOS], dtype=float)
    por_turno = rng.multinomial(n, capacidade / capacidade.sum())
    partes = [inicio + (fim - inicio - ATENDIMENTO_MIN) * rng.random(q)
              for q, (_, inicio, fim, _k) in zip(por_turno, TURNOS, strict=True)]
    resultado = np.concatenate(partes)
    rng.shuffle(resultado)
    return resultado


def dia_de_pico(gold: Path = GOLD) -> tuple[str, str, np.ndarray]:
    fato = pd.read_parquet(gold / "fato_atendimento.parquet", columns=["data", "ubs", "hora_chegada"])
    data, ubs = fato.groupby(["data", "ubs"]).size().idxmax()
    pico = fato[(fato["data"] == data) & (fato["ubs"] == ubs)]
    return str(data), ubs, (pico["hora_chegada"].dt.hour * 60 + pico["hora_chegada"].dt.minute).to_numpy(dtype=float)


def rodar(minutos: np.ndarray, rodadas: int = RODADAS, seed: int = 42) -> dict:
    rng = np.random.default_rng(seed)
    antes, atendidos_antes = [], []
    depois = {a: ([], []) for a in ADESOES}
    for _ in range(rodadas):
        chegadas = rng.choice(minutos, PESSOAS, replace=True)
        duracoes = rng.exponential(ATENDIMENTO_MIN, PESSOAS)
        espera, atendidos = simular_fila(chegadas, duracoes)
        antes.append(espera)
        atendidos_antes.append(atendidos)
        novos = chegadas_por_turno(PESSOAS, rng)
        for adesao, (esperas, atend) in depois.items():
            mistas = np.where(rng.random(PESSOAS) < adesao, novos, chegadas)
            espera, atendidos = simular_fila(mistas, duracoes)
            esperas.append(espera)
            atend.append(atendidos)
    base = float(np.mean(antes))
    return {
        "pessoas": PESSOAS, "rodadas": rodadas, "atendimento_medio_min": ATENDIMENTO_MIN,
        "antes_fila_por_chegada": {"espera_media_min": round(base, 1),
                                   "atendidos": round(float(np.mean(atendidos_antes)), 1)},
        "depois_por_adesao": {
            f"{int(a * 100)}%": {"espera_media_min": round(float(np.mean(e)), 1),
                                 "atendidos": round(float(np.mean(t)), 1),
                                 "reducao_pct": round(100 * (base - float(np.mean(e))) / base, 1)}
            for a, (e, t) in depois.items()
        },
        "dados": "simulação sobre dataset sintético; não é medição em UBS real",
    }


def main() -> None:
    data, ubs, minutos = dia_de_pico()
    r = {"dia_de_pico": data, "ubs": ubs, **rodar(minutos)}
    SAIDA.write_text(json.dumps(r, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"dia de pico: {data} ({ubs})")
    print(f"antes: espera média {r['antes_fila_por_chegada']['espera_media_min']} min")
    for adesao, v in r["depois_por_adesao"].items():
        print(f"depois, adesão {adesao}: {v['espera_media_min']} min (-{v['reducao_pct']}%), "
              f"atendidos {v['atendidos']}")


if __name__ == "__main__":
    main()
