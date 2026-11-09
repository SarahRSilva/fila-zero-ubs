"""Configuração lida de variáveis de ambiente. Nenhum segredo fica no código."""
import os

UBS = ["UBS Jardim Esperanca", "UBS Vila Nova"]
TURNOS = ("manha", "tarde", "noite")
CORES = ("verde", "amarelo", "vermelho")


def _url_banco() -> str:
    url = os.getenv("DATABASE_URL", "sqlite:///./filazero.db")
    # Render/Railway entregam postgres:// ou postgresql://; o driver usado aqui é o psycopg 3
    for prefixo in ("postgres://", "postgresql://"):
        if url.startswith(prefixo):
            return "postgresql+psycopg://" + url[len(prefixo):]
    return url


DATABASE_URL = _url_banco()
JWT_SECRET = os.getenv("JWT_SECRET", "")
JWT_EXPIRA_MIN = int(os.getenv("JWT_EXPIRA_MIN", "60"))
PSEUDONIMO_SAL = os.getenv("PSEUDONIMO_SAL", "")
SEED_SENHA = os.getenv("SEED_SENHA", "")  # se vazio, não cria os usuários de demonstração
CORS_ORIGENS = [o.strip() for o in os.getenv("CORS_ORIGENS", "http://localhost:5173").split(",") if o.strip()]

if len(JWT_SECRET) < 32:
    raise RuntimeError("Defina JWT_SECRET com pelo menos 32 caracteres (veja .env.example).")
if not PSEUDONIMO_SAL:
    raise RuntimeError("Defina PSEUDONIMO_SAL (veja .env.example).")
