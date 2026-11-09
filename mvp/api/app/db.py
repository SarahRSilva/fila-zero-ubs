"""Banco operacional (PostgreSQL em produção, SQLite nos testes)."""
from __future__ import annotations

from datetime import date, datetime, time, timezone

from sqlalchemy import Boolean, Date, DateTime, Float, ForeignKey, Integer, String, Time, create_engine, select
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker

from . import config
from .seguranca import gerar_hash_senha

engine = create_engine(config.DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(engine, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


class Usuario(Base):
    __tablename__ = "usuario"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    nome: Mapped[str] = mapped_column(String(80))
    senha_hash: Mapped[str] = mapped_column(String(80))
    perfil: Mapped[str] = mapped_column(String(10))  # cidadao | gestora
    ubs: Mapped[str | None] = mapped_column(String(60), nullable=True)


class Atendimento(Base):
    __tablename__ = "atendimento"

    id: Mapped[int] = mapped_column(primary_key=True)
    usuario_id: Mapped[int] = mapped_column(ForeignKey("usuario.id"), index=True)
    cidadao_hash: Mapped[str] = mapped_column(String(16), index=True)  # é o que vai para o lake
    ubs: Mapped[str] = mapped_column(String(60), index=True)
    data: Mapped[date] = mapped_column(Date, index=True)
    turno: Mapped[str] = mapped_column(String(10))
    hora_chegada: Mapped[time | None] = mapped_column(Time, nullable=True)
    hora_atendimento: Mapped[time | None] = mapped_column(Time, nullable=True)
    espera_min: Mapped[int | None] = mapped_column(Integer, nullable=True)
    motivo: Mapped[str] = mapped_column(String(200))
    cor_triagem: Mapped[str] = mapped_column(String(10))
    atendido: Mapped[bool] = mapped_column(Boolean, default=False)
    criado_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class LeituraSala(Base):
    __tablename__ = "leitura_sala"

    id: Mapped[int] = mapped_column(primary_key=True)
    ubs: Mapped[str] = mapped_column(String(60), index=True)
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    ocupacao: Mapped[int] = mapped_column(Integer)
    capacidade: Mapped[int] = mapped_column(Integer)
    temperatura: Mapped[float | None] = mapped_column(Float, nullable=True)
    alerta: Mapped[bool] = mapped_column(Boolean, default=False)
    origem: Mapped[str] = mapped_column(String(20), default="desconhecida")


def get_db():
    with SessionLocal() as sessao:
        yield sessao


def iniciar_banco() -> None:
    """Cria as tabelas e, se SEED_SENHA estiver definida, os dois usuários de demonstração."""
    Base.metadata.create_all(engine)
    if not config.SEED_SENHA:
        return
    with SessionLocal() as sessao:
        if sessao.scalar(select(Usuario.id).limit(1)) is not None:
            return
        senha = gerar_hash_senha(config.SEED_SENHA)
        sessao.add_all([
            Usuario(email="cidadao@filazero.dev", nome="Cidadã Demo", senha_hash=senha, perfil="cidadao"),
            Usuario(email="gestora@filazero.dev", nome="Gestora Demo", senha_hash=senha, perfil="gestora",
                    ubs=config.UBS[0]),
        ])
        sessao.commit()


def buscar_usuario(sessao: Session, email: str) -> Usuario | None:
    return sessao.scalar(select(Usuario).where(Usuario.email == email.lower()))
