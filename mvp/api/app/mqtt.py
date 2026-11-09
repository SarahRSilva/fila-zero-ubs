"""Assinante MQTT da API: guarda a última leitura de cada sala e grava no banco.

Roda em uma thread própria (paho) durante a vida da aplicação. Se o broker não
estiver acessível, a API sobe mesmo assim e /sala/agora responde 404 até
chegar a primeira leitura.
"""
from __future__ import annotations

import json
import logging
import os
import threading
from datetime import datetime, timezone

import paho.mqtt.client as mqtt

from .db import LeituraSala, SessionLocal

log = logging.getLogger("filazero.mqtt")

MQTT_HOST = os.getenv("MQTT_HOST", "")
MQTT_PORT = int(os.getenv("MQTT_PORT", "1883"))
MQTT_TOPICO = os.getenv("MQTT_TOPICO", "filazero/ubs/+/sala")

_ultimas: dict[str, dict] = {}
_trava = threading.Lock()
_cliente: mqtt.Client | None = None


def _hora(ts: str | None) -> datetime:
    if ts:
        try:
            dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
            return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
        except ValueError:
            pass
    return datetime.now(timezone.utc)


def registrar_leitura(corpo: dict, topico: str = "") -> dict:
    """Valida, guarda em memória e grava no banco. Usado pelo MQTT e pelo POST /sala."""
    ubs = str(corpo.get("ubs") or "").strip()
    ocupacao, capacidade = int(corpo["ocupacao"]), int(corpo["capacidade"])
    if not ubs or ocupacao < 0 or capacidade <= 0:
        raise ValueError("leitura sem ubs ou com ocupação/capacidade inválida")
    temperatura = corpo.get("temperatura")
    leitura = {
        "ubs": ubs,
        "ocupacao": ocupacao,
        "capacidade": capacidade,
        "taxa_ocupacao": round(ocupacao / capacidade, 3),
        "alerta": ocupacao >= capacidade * 0.9,
        "temperatura": float(temperatura) if temperatura is not None else None,
        "origem": str(corpo.get("origem") or "desconhecida"),
        "ts": _hora(corpo.get("ts")),
        "topico": topico,
    }
    with _trava:
        _ultimas[ubs] = leitura
    with SessionLocal() as sessao:
        sessao.add(LeituraSala(**{k: v for k, v in leitura.items() if k not in ("taxa_ocupacao", "topico")}))
        sessao.commit()
    return leitura


def ultima(ubs: str) -> dict | None:
    with _trava:
        return _ultimas.get(ubs)


def _ao_receber(_c, _u, msg):
    try:
        leitura = registrar_leitura(json.loads(msg.payload), msg.topic)
        log.info("sala %s: %d/%d%s", leitura["ubs"], leitura["ocupacao"], leitura["capacidade"],
                 " ALERTA" if leitura["alerta"] else "")
    except (ValueError, KeyError, TypeError) as erro:
        log.warning("leitura ignorada em %s: %s", msg.topic, erro)


def iniciar() -> None:
    """Conecta ao broker em segundo plano. Sem MQTT_HOST, não faz nada."""
    global _cliente
    if not MQTT_HOST:
        log.info("MQTT desligado (MQTT_HOST vazio)")
        return
    _cliente = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=f"filazero-api-{os.getpid()}")
    _cliente.on_message = _ao_receber
    _cliente.on_connect = lambda c, *_: (c.subscribe(MQTT_TOPICO), log.info("MQTT assinando %s", MQTT_TOPICO))
    _cliente.reconnect_delay_set(min_delay=1, max_delay=30)
    try:
        _cliente.connect_async(MQTT_HOST, MQTT_PORT, keepalive=30)
        _cliente.loop_start()
    except (OSError, ValueError) as erro:
        log.warning("MQTT indisponível em %s:%s (%s); seguindo sem sensor", MQTT_HOST, MQTT_PORT, erro)


def parar() -> None:
    if _cliente:
        _cliente.loop_stop()
        _cliente.disconnect()
