"""API do Fila Zero UBS: login, atendimento e previsão de demanda."""
from __future__ import annotations

import json
import logging
import math
import time
from contextlib import asynccontextmanager
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import func
from functools import lru_cache

from fastapi import Depends, FastAPI, HTTPException, Query, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from ia.previsao import Previsor
from ia.triagem_llm import classificar_com_llm

from . import config, mqtt, seguranca
from .db import Atendimento, LeituraSala, Usuario, buscar_usuario, get_db, iniciar_banco
from .schemas import (AtendimentoEntrada, AtendimentoSaida, CadastroEntrada, LeituraSalaEntrada, LoginEntrada,
                      LoginSaida, PrevisaoSaida, SalaAgora, TriagemEntrada, TriagemSaida)

FUSO_BRASIL = timezone(timedelta(hours=-3))  # sem depender de tzdata na imagem; o Brasil não tem horário de verão
log = logging.getLogger("filazero.api")
logging.basicConfig(level=logging.INFO, format="%(message)s")


@asynccontextmanager
async def lifespan(_: FastAPI):
    iniciar_banco()
    mqtt.iniciar()
    yield
    mqtt.parar()


app = FastAPI(title="Fila Zero UBS", version="0.4.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=config.CORS_ORIGENS,
    # celular/tablet na mesma rede Wi-Fi abrindo o front pelo IP da máquina (só redes privadas)
    allow_origin_regex=r"^https?://(localhost|127\.0\.0\.1|10\.\d+\.\d+\.\d+|192\.168\.\d+\.\d+|172\.(1[6-9]|2\d|3[01])\.\d+\.\d+)(:\d+)?$",
    allow_methods=["GET", "POST"],
    allow_headers=["Authorization", "Content-Type"],
)
bearer = HTTPBearer(auto_error=False, description="Token devolvido por POST /login")


@app.middleware("http")
async def log_estruturado(request: Request, call_next):
    inicio = time.perf_counter()
    resposta = await call_next(request)
    log.info(json.dumps({
        "hora": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "metodo": request.method,
        "rota": request.url.path,
        "status": resposta.status_code,
        "ms": round((time.perf_counter() - inicio) * 1000, 1),
    }))
    return resposta


def usuario_logado(credenciais: HTTPAuthorizationCredentials | None = Depends(bearer),
                   db: Session = Depends(get_db)) -> Usuario:
    nao_autorizado = HTTPException(status.HTTP_401_UNAUTHORIZED, "Token ausente, inválido ou expirado",
                                   headers={"WWW-Authenticate": "Bearer"})
    dados = seguranca.ler_token(credenciais.credentials) if credenciais else None
    if not dados:
        raise nao_autorizado
    usuario = db.get(Usuario, int(dados["sub"]))
    if usuario is None:
        raise nao_autorizado
    return usuario


@lru_cache(maxsize=1)
def previsor() -> Previsor:
    return Previsor.carregar()


@app.get("/health", tags=["monitoramento"])
def health() -> dict:
    return {"status": "ok", "servico": "fila-zero-api", "versao": app.version,
            "hora": datetime.now(timezone.utc).isoformat()}


@app.get("/ubs", tags=["cadastro"])
def listar_ubs() -> list[str]:
    return config.UBS


def _resposta_login(usuario: Usuario) -> LoginSaida:
    return LoginSaida(access_token=seguranca.criar_token(usuario.id, usuario.perfil),
                      expira_em_min=config.JWT_EXPIRA_MIN, nome=usuario.nome,
                      perfil=usuario.perfil, ubs=usuario.ubs)


@app.post("/cadastro", response_model=LoginSaida, status_code=status.HTTP_201_CREATED, tags=["acesso"])
def cadastrar(entrada: CadastroEntrada, db: Session = Depends(get_db)):
    """Cria uma conta de cidadão e já devolve o token. Gestora não se cadastra por aqui."""
    if buscar_usuario(db, entrada.email):
        raise HTTPException(status.HTTP_409_CONFLICT, "Já existe uma conta com este e-mail")
    usuario = Usuario(email=entrada.email.lower(), nome=entrada.nome, perfil="cidadao",
                      senha_hash=seguranca.gerar_hash_senha(entrada.senha))
    db.add(usuario)
    db.commit()
    return _resposta_login(usuario)


@app.post("/login", response_model=LoginSaida, tags=["acesso"])
def login(entrada: LoginEntrada, db: Session = Depends(get_db)):
    # Por conta, não por IP: atrás do Docker ou de um proxy todos chegam com o mesmo endereço.
    chave = entrada.email.lower()
    if (espera := seguranca.espera_login(chave)) > 0:
        segundos = math.ceil(espera)
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS,
                            f"Muitas tentativas seguidas. Tente de novo em {segundos} s.",
                            headers={"Retry-After": str(segundos)})
    usuario = buscar_usuario(db, entrada.email)
    if not seguranca.senha_confere(entrada.senha, usuario.senha_hash if usuario else None):
        seguranca.registrar_falha_login(chave)
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "E-mail ou senha incorretos")
    seguranca.limpar_falhas_login(chave)
    return _resposta_login(usuario)


def _exigir_unidade_da_gestora(usuario: Usuario, ubs: str) -> None:
    if usuario.perfil == "gestora" and ubs != usuario.ubs:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "A gestora só acessa os dados da própria unidade")


@app.post("/atendimento", response_model=AtendimentoSaida, status_code=status.HTTP_201_CREATED,
          tags=["atendimento"])
def registrar_atendimento(entrada: AtendimentoEntrada, usuario: Usuario = Depends(usuario_logado),
                          db: Session = Depends(get_db)):
    """Registra o atendimento. O cidadão tem um por dia e unidade: confirmar de novo troca o turno."""
    _exigir_unidade_da_gestora(usuario, entrada.ubs)
    if usuario.perfil == "cidadao" and entrada.data < datetime.now(FUSO_BRASIL).date():
        raise HTTPException(422, "Não é possível marcar uma data que já passou")
    try:
        fechada = previsor().motivo_fechada(entrada.data)
    except FileNotFoundError:
        fechada = None
    if fechada:
        raise HTTPException(422, f"A UBS não abre nesse dia ({fechada})")

    atendimento = None
    if usuario.perfil == "cidadao":
        atendimento = db.scalar(select(Atendimento).where(Atendimento.usuario_id == usuario.id,
                                                          Atendimento.data == entrada.data,
                                                          Atendimento.ubs == entrada.ubs))
    if atendimento:
        for campo, valor in entrada.model_dump().items():
            setattr(atendimento, campo, valor)
    else:
        atendimento = Atendimento(**entrada.model_dump(), usuario_id=usuario.id,
                                  cidadao_hash=seguranca.pseudonimo(usuario.id))
        db.add(atendimento)
    db.commit()
    return atendimento


@app.get("/atendimento", response_model=list[AtendimentoSaida], tags=["atendimento"])
def listar_atendimentos(data: date | None = None, ubs: str | None = None,
                        usuario: Usuario = Depends(usuario_logado), db: Session = Depends(get_db)):
    """A gestora vê os atendimentos da unidade; o cidadão vê só os dele."""
    consulta = select(Atendimento).order_by(Atendimento.data.desc(), Atendimento.id.desc()).limit(500)
    if usuario.perfil == "gestora":
        if ubs:
            _exigir_unidade_da_gestora(usuario, ubs)
        consulta = consulta.where(Atendimento.ubs == usuario.ubs)
    else:
        consulta = consulta.where(Atendimento.usuario_id == usuario.id)
    if data:
        consulta = consulta.where(Atendimento.data == data)
    return db.scalars(consulta).all()


@app.get("/previsao", response_model=PrevisaoSaida, tags=["previsao"])
def prever_demanda(
    data: date = Query(description="Dia a prever, AAAA-MM-DD"),
    ubs: str | None = Query(default=None, description="Padrão: a UBS da gestora ou a primeira da lista"),
    temp_max: float | None = Query(default=None, ge=-10, le=50, description="Previsão do tempo, se houver"),
    chuva_mm: float | None = Query(default=None, ge=0, le=500),
    usuario: Usuario = Depends(usuario_logado),
):
    """Quantas pessoas devem procurar a UBS em cada turno do dia pedido."""
    ubs = ubs or usuario.ubs or config.UBS[0]
    if ubs not in config.UBS:
        raise HTTPException(422, f"UBS desconhecida. Opções: {', '.join(config.UBS)}")
    try:
        modelo = previsor()
    except FileNotFoundError:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE,
                            "Modelo não encontrado. Rode ia/treinar.py.") from None
    fechada = modelo.motivo_fechada(data)
    return PrevisaoSaida(
        data=data, ubs=ubs, aberta=fechada is None, motivo_fechada=fechada,
        turnos=modelo.prever(data, ubs, temp_max, chuva_mm),
        modelo=modelo.metricas["modelo"], mae_teste=modelo.metricas["teste"]["mae_geral"],
    )


@app.post("/triagem", response_model=TriagemSaida, tags=["triagem"])
def pre_triagem(entrada: TriagemEntrada, usuario: Usuario = Depends(usuario_logado)):
    """Classifica o relato em verde, amarelo ou vermelho e sugere o turno.

    Não é diagnóstico nem substitui a classificação de risco do enfermeiro.
    Usa o agente com LLM se ANTHROPIC_API_KEY estiver definida; as regras são sempre o piso de segurança.
    """
    return classificar_com_llm(entrada.relato, entrada.resposta_anterior)


def _sala_agora(ubs: str, db: Session) -> SalaAgora:
    leitura = mqtt.ultima(ubs)
    if leitura is None:  # nada chegou pelo MQTT desde que a API subiu: tenta o banco
        registro = db.scalar(select(LeituraSala).where(LeituraSala.ubs == ubs).order_by(LeituraSala.ts.desc()).limit(1))
        if registro is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Nenhuma leitura do sensor para esta UBS")
        campos = ("ubs", "ocupacao", "capacidade", "temperatura", "alerta", "origem", "ts")
        leitura = {c: getattr(registro, c) for c in campos}
        leitura["taxa_ocupacao"] = round(registro.ocupacao / registro.capacidade, 3)
    agora = datetime.now(timezone.utc)
    ts = leitura["ts"] if leitura["ts"].tzinfo else leitura["ts"].replace(tzinfo=timezone.utc)
    inicio_dia = datetime.combine(agora.date(), datetime.min.time(), tzinfo=timezone.utc)
    alertas_hoje = db.scalar(select(func.count()).select_from(LeituraSala)
                             .where(LeituraSala.ubs == ubs, LeituraSala.alerta.is_(True), LeituraSala.ts >= inicio_dia))
    return SalaAgora(**{k: v for k, v in leitura.items() if k != "topico"},
                     segundos_atras=max(0, int((agora - ts).total_seconds())), alertas_hoje=alertas_hoje or 0)


@app.get("/sala/agora", response_model=SalaAgora, tags=["sala de espera"])
def sala_agora(ubs: str | None = None, usuario: Usuario = Depends(usuario_logado), db: Session = Depends(get_db)):
    """Última leitura do sensor de lotação da sala de espera."""
    return _sala_agora(ubs or usuario.ubs or config.UBS[0], db)


@app.post("/sala", response_model=SalaAgora, status_code=status.HTTP_201_CREATED, tags=["sala de espera"])
def receber_leitura(entrada: LeituraSalaEntrada, usuario: Usuario = Depends(usuario_logado),
                    db: Session = Depends(get_db)):
    """Recebe uma leitura por HTTP (mesmo formato do MQTT), para ambientes sem broker."""
    if usuario.perfil != "gestora":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Só a gestora pode enviar leituras")
    _exigir_unidade_da_gestora(usuario, entrada.ubs)
    corpo = entrada.model_dump()
    corpo["ts"] = corpo["ts"].isoformat() if corpo["ts"] else None
    mqtt.registrar_leitura(corpo, "http")
    return _sala_agora(entrada.ubs, db)
