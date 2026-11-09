"""Ambiente dos testes: banco SQLite temporário e segredos só de teste.

As variáveis precisam existir antes de `app` ser importado.
"""
import os
import tempfile
from pathlib import Path

_tmp = Path(tempfile.mkdtemp(prefix="filazero-testes-"))
os.environ["DATABASE_URL"] = f"sqlite:///{_tmp / 'teste.db'}"
os.environ["JWT_SECRET"] = "segredo-usado-somente-nos-testes-0123456789"
os.environ["PSEUDONIMO_SAL"] = "sal-de-teste"
os.environ["SEED_SENHA"] = "senha-de-teste"

import pytest  # noqa: E402
from app.main import app  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402


@pytest.fixture(scope="session")
def cliente():
    with TestClient(app) as c:
        yield c


def _token(cliente, email):
    r = cliente.post("/login", json={"email": email, "senha": os.environ["SEED_SENHA"]})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


@pytest.fixture(scope="session")
def cidadao(cliente):
    return _token(cliente, "cidadao@filazero.dev")


@pytest.fixture(scope="session")
def gestora(cliente):
    return _token(cliente, "gestora@filazero.dev")
