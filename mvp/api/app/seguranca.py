"""Senha (bcrypt), token (JWT) e pseudonimização do cidadão."""
from __future__ import annotations

import hashlib
import time
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt

from . import config

ALGORITMO = "HS256"


def gerar_hash_senha(senha: str) -> str:
    return bcrypt.hashpw(senha.encode(), bcrypt.gensalt()).decode()


# comparado quando o e-mail não existe, para o login levar o mesmo tempo nos dois casos
_HASH_FALSO = gerar_hash_senha("usuario-inexistente")


def senha_confere(senha: str, senha_hash: str | None) -> bool:
    try:
        confere = bcrypt.checkpw(senha.encode(), (senha_hash or _HASH_FALSO).encode())
    except ValueError:  # bcrypt recusa senha acima de 72 bytes
        return False
    return confere and senha_hash is not None


# Espera crescente por conta: as primeiras falhas são livres; depois cada nova tentativa
# precisa esperar 1 s, 2 s, 4 s... até ESPERA_MAX_S. Força bruta fica inviável, e quem
# errar de propósito a senha de outra pessoa a atrasa no máximo ESPERA_MAX_S, sem travar a conta.
FALHAS_LIVRES, ESPERA_MAX_S, ESQUECER_APOS_S = 3, 60, 900
_falhas: dict[str, tuple[int, float]] = {}  # chave -> (falhas seguidas, hora da última)


def espera_login(chave: str) -> float:
    """Segundos que a chave ainda precisa esperar antes de tentar de novo (0 = pode tentar)."""
    falhas, ultima = _falhas.get(chave, (0, 0.0))
    agora = time.monotonic()
    if falhas and agora - ultima > ESQUECER_APOS_S:
        _falhas.pop(chave, None)
        return 0.0
    if falhas < FALHAS_LIVRES:
        return 0.0
    return max(0.0, ultima + min(2 ** (falhas - FALHAS_LIVRES), ESPERA_MAX_S) - agora)


def registrar_falha_login(chave: str) -> None:
    if len(_falhas) > 10_000:  # teto de memória; a API roda em um processo só
        _falhas.clear()
    falhas, _ = _falhas.get(chave, (0, 0.0))
    _falhas[chave] = (falhas + 1, time.monotonic())


def limpar_falhas_login(chave: str) -> None:
    _falhas.pop(chave, None)


def criar_token(usuario_id: int, perfil: str) -> str:
    agora = datetime.now(timezone.utc)
    dados = {"sub": str(usuario_id), "perfil": perfil, "iat": agora,
             "exp": agora + timedelta(minutes=config.JWT_EXPIRA_MIN)}
    return jwt.encode(dados, config.JWT_SECRET, algorithm=ALGORITMO)


def ler_token(token: str) -> dict | None:
    try:
        return jwt.decode(token, config.JWT_SECRET, algorithms=[ALGORITMO], options={"require": ["exp", "sub"]})
    except jwt.PyJWTError:
        return None


def pseudonimo(usuario_id: int) -> str:
    """Identificador que vai para o lake no lugar de qualquer dado pessoal."""
    return hashlib.sha256(f"{config.PSEUDONIMO_SAL}:{usuario_id}".encode()).hexdigest()[:16]
