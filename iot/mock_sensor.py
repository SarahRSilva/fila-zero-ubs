"""Simula o sensor da sala de espera publicando no Mosquitto, sem placa.

Uso:
    python iot/mock_sensor.py                          # UBS Jardim Esperanca, a cada 5 s
    python iot/mock_sensor.py --todas --intervalo 2    # as duas UBS
    python iot/mock_sensor.py --hora 6.5               # começa a simulação às 6h30 (padrão: hora atual)
    python iot/mock_sensor.py --acelerar 60            # 1 s real = 1 min simulado

Mesmo tópico e mesmo JSON do sketch do ESP32 (iot/README.md).
"""
from __future__ import annotations

import argparse
import json
import math
import os
import random
import time
from datetime import datetime, timezone

import paho.mqtt.client as mqtt

UBS = {
    "jardim-esperanca": {"nome": "UBS Jardim Esperanca", "capacidade": 30},
    "vila-nova": {"nome": "UBS Vila Nova", "capacidade": 20},
}
LIMITE = 0.90


def ocupacao_esperada(hora: float, capacidade: int) -> float:
    """Curva da manhã de fila: enche a partir das 5h, pico às 7h, esvazia até 12h;
    tarde e noite com picos menores."""
    picos = [(7.0, 1.3, 1.2), (13.0, 0.8, 1.0), (18.0, 0.5, 0.9)]  # (centro, altura, largura em horas)
    f = sum(a * math.exp(-((hora - c) ** 2) / (2 * larg * larg)) for c, a, larg in picos)
    return min(capacidade * 1.2, capacidade * f)


def leitura(ubs_id: str, hora: float, estado: dict) -> dict:
    cfg = UBS[ubs_id]
    alvo = ocupacao_esperada(hora, cfg["capacidade"])
    # ocupação anda em direção ao alvo com um pouco de ruído
    delta = alvo - estado["ocupacao"]
    passo = int(round(delta * 0.3 + random.gauss(0, 1.2)))
    if passo > 0:
        estado["entradas"] += passo
    else:
        estado["saidas"] += -passo
    estado["ocupacao"] = max(0, estado["ocupacao"] + passo)
    temperatura = 23.5 + 4.5 * math.exp(-((hora - 15) ** 2) / 18) + 0.08 * estado["ocupacao"] + random.gauss(0, 0.2)
    return {
        "ubs": cfg["nome"],
        "ocupacao": estado["ocupacao"],
        "capacidade": cfg["capacidade"],
        "temperatura": round(temperatura, 1),
        "entradas": estado["entradas"],
        "saidas": estado["saidas"],
        "alerta": estado["ocupacao"] >= cfg["capacidade"] * LIMITE,
        "origem": "mock",
        "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }


def main() -> None:
    ap = argparse.ArgumentParser(description="Mock do sensor de lotação")
    ap.add_argument("--host", default=os.getenv("MQTT_HOST", "localhost"))
    ap.add_argument("--porta", type=int, default=int(os.getenv("MQTT_PORT", "1883")))
    ap.add_argument("--ubs", default="jardim-esperanca", choices=list(UBS))
    ap.add_argument("--todas", action="store_true")
    ap.add_argument("--intervalo", type=float, default=5.0, help="segundos reais entre leituras")
    ap.add_argument("--hora", type=float, default=None, help="hora simulada inicial, ex.: 6.5")
    ap.add_argument("--acelerar", type=float, default=1.0, help="minutos simulados por segundo real")
    ap.add_argument("--leituras", type=int, default=0, help="para depois de N leituras (0 = sem parar)")
    ap.add_argument("--seed", type=int, default=None)
    args = ap.parse_args()
    random.seed(args.seed)

    cliente = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=f"mock-sensor-{os.getpid()}")
    cliente.connect(args.host, args.porta, keepalive=30)
    cliente.loop_start()

    agora = datetime.now()
    hora = args.hora if args.hora is not None else agora.hour + agora.minute / 60
    ids = list(UBS) if args.todas else [args.ubs]
    estados = {u: {"ocupacao": int(ocupacao_esperada(hora, UBS[u]["capacidade"])), "entradas": 0, "saidas": 0}
               for u in ids}
    print(f"publicando em mqtt://{args.host}:{args.porta} para {', '.join(ids)} (Ctrl+C para parar)")

    n = 0
    try:
        while not args.leituras or n < args.leituras:
            for u in ids:
                corpo = leitura(u, hora % 24, estados[u])
                cliente.publish(f"filazero/ubs/{u}/sala", json.dumps(corpo), qos=0, retain=True)
                print(f"{corpo['ts']} {u:<17} {corpo['ocupacao']:>3}/{corpo['capacidade']} "
                      f"{corpo['temperatura']:>5} °C {'ALERTA' if corpo['alerta'] else ''}")
            n += 1
            hora += args.intervalo * args.acelerar / 60
            time.sleep(args.intervalo)
    except KeyboardInterrupt:
        pass
    finally:
        cliente.loop_stop()
        cliente.disconnect()


if __name__ == "__main__":
    main()
