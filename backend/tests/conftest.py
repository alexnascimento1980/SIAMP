import os

os.environ.setdefault("JWT_SECRET_KEY", "chave-de-teste-nao-usar-em-producao")
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
# TestClient fala por HTTP puro (sem TLS); cookies "Secure" não seriam
# aceitos/enviados pelo cliente de teste, então usamos o mesmo valor do
# ambiente de desenvolvimento local.
os.environ.setdefault("COOKIE_SECURE", "false")

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base, get_db
from app.core.rate_limit import limiter
from app.core.security import gerar_hash_senha
from app.main import app
from app.models.usuario import Usuario

engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)


@event.listens_for(engine, "connect")
def _ativar_chaves_estrangeiras_sqlite(conexao_dbapi, _registro_conexao):
    # SQLite não valida chaves estrangeiras por padrão (diferente do
    # Postgres, que bloqueia por padrão - RESTRICT - a menos que a FK
    # seja explicitamente configurada com ON DELETE). Sem isso, um bug
    # real de FK (ex.: tentar excluir um usuário referenciado por um
    # turno) passa despercebido pelos testes e só aparece em produção.
    cursor = conexao_dbapi.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture()
def db_session():
    Base.metadata.create_all(bind=engine)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture()
def client(db_session):
    def _override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = _override_get_db
    limiter.reset()  # evita que o rate limit de um teste vaze para o próximo
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture()
def usuario_teste(db_session):
    usuario = Usuario(
        nome="Operador Teste",
        email="operador@siamp.test",
        senha_hash=gerar_hash_senha("senha-forte-123"),
        perfil="OPERADOR",
        ativo=True,
    )
    db_session.add(usuario)
    db_session.commit()
    db_session.refresh(usuario)
    return usuario
