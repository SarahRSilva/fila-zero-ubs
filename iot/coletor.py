"""Assina o tópico do sensor e grava as leituras na camada bronze do lake.

Uso:
    python iot/coletor.py            # grava em bigdata/lake/bronze/lotacao_YYYY-MM.csv

É a ponta de ingestão do Big Data: nada aqui passa pela API.
"""
from __future__ import annotations

import csv
import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path

import paho.mqtt.client as mqtt

RAIZ = Path(__file__).resolve().parents[1]
BRONZE = Path(os.getenv("LAKE_BRONZE", RAIZ / "bigdata" / "lake" / "bronze"))
COLUNAS = ["ts", "ubs", "ocupacao", "capacidade", "temperatura", "entradas", "saidas", "alerta", "origem"]
log = logging.getLogger("coletor")


def gravar(corpo: dict, bronze: Path = BRONZE) -> Path:
    ts = corpo.get("ts") or datetime.now(timezone.utc).isoformat(timespec="seconds")
    linha = {c: corpo.get(c, "") for c in COLUNAS}
    linha["ts"] = ts
    linha["alerta"] = "S" if corpo.get("alerta") else "N"
    arquivo = bronze / f"lotacao_{ts[:7]}.csv"
    novo = not arquivo.exists()
    bronze.mkdir(parents=True, exist_ok=True)
    with arquivo.open("a", newline="") as f:
        escritor = csv.DictWriter(f, fieldnames=COLUNAS)
        if novo:
            escritor.writeheader()
        escritor.writerow(linha)
    return arquivo


def ao_receber(_cliente, _dados, msg):
    try:
        corpo = json.loads(msg.payload)
        arquivo = gravar(corpo)
        log.info("%s %s %s/%s -> %s", msg.topic, corpo.get("ubs"), corpo.get("ocupacao"),
                 corpo.get("capacidade"), arquivo.name)
    except (ValueError, KeyError) as erro:
        log.warning("mensagem ignorada em %s: %s", msg.topic, erro)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)-7s %(name)s %(message)s")
    host, porta = os.getenv("MQTT_HOST", "localhost"), int(os.getenv("MQTT_PORT", "1883"))
    topico = os.getenv("MQTT_TOPICO", "filazero/ubs/+/sala")
    cliente = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=f"coletor-{os.getpid()}")
    cliente.on_message = ao_receber
    cliente.connect(host, porta, keepalive=30)
    cliente.subscribe(topico, qos=0)
    log.info("assinando %s em mqtt://%s:%s, gravando em %s", topico, host, porta, BRONZE)
    cliente.loop_forever()


if __name__ == "__main__":
    main()
