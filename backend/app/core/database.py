import asyncio
import os

from fastapi.concurrency import run_in_threadpool
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql+psycopg2://siamp_user:siamp_password@localhost:5432/siamp_db")

# pool_size/max_overflow são específicos do QueuePool (usado em Postgres) e
# quebram a criação da engine em SQLite (usado nos testes, que roda com
# SingletonThreadPool/StaticPool). Por isso só são aplicados fora do SQLite.
_eh_sqlite = DATABASE_URL.startswith("sqlite")


def _inteiro_do_ambiente(nome: str, padrao: int) -> int:
    try:
        return max(0, int(os.getenv(nome, padrao)))
    except ValueError:
        return padrao


_engine_kwargs = {"pool_pre_ping": True}  # Testa a conexão antes de executar query (evita conexões mortas)
if not _eh_sqlite:
    # Teto de conexões por processo = DB_POOL_SIZE + DB_MAX_OVERFLOW (padrão
    # 5 + 5 = 10). Precisa ficar ABAIXO do limite do banco/pooler: o
    # Supabase em "session mode" (porta 5432 do pooler) aceita só 15
    # clientes simultâneos no plano gratuito, e passar disso derruba a
    # requisição com EMAXCONNSESSION (erro 500). Com o teto baixo, o
    # excesso de requisições simultâneas ESPERA por uma conexão livre
    # (até DB_POOL_TIMEOUT segundos) em vez de falhar. Antes eram 10 + 20,
    # bem acima do limite do pooler.
    _engine_kwargs["pool_size"] = _inteiro_do_ambiente("DB_POOL_SIZE", 5)
    _engine_kwargs["max_overflow"] = _inteiro_do_ambiente("DB_MAX_OVERFLOW", 5)
    _engine_kwargs["pool_timeout"] = _inteiro_do_ambiente("DB_POOL_TIMEOUT", 30)
    # Devolve ao pooler conexões paradas há muito tempo, liberando vaga.
    _engine_kwargs["pool_recycle"] = _inteiro_do_ambiente("DB_POOL_RECYCLE", 1800)

# Pool de conexões otimizado para requisições concorrentes
engine = create_engine(DATABASE_URL, **_engine_kwargs)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

# Quantas sessões podem estar abertas ao mesmo tempo = teto do pool. Os
# pedidos que passam disso ESPERAM aqui (de forma assíncrona, sem ocupar
# thread nem conexão) em vez de brigar pelo pool dentro das threads do
# FastAPI. Sem isto, com mais pedidos simultâneos que conexões, as threads
# ficavam todas bloqueadas esperando conexão enquanto os pedidos que já
# tinham conexão esperavam uma thread para terminar - um impasse que só se
# desfazia no pool_timeout (30 s) e terminava em erro 500.
_LIMITE_SESSOES = None if _eh_sqlite else (_engine_kwargs["pool_size"] + _engine_kwargs["max_overflow"]) or None
_semaforo_sessoes: asyncio.Semaphore | None = None


# Dependência do FastAPI para injetar a sessão do banco nas rotas
async def get_db():
    global _semaforo_sessoes
    if _LIMITE_SESSOES is None:
        db = SessionLocal()
        try:
            yield db
        finally:
            await run_in_threadpool(db.close)
        return

    if _semaforo_sessoes is None:
        _semaforo_sessoes = asyncio.Semaphore(_LIMITE_SESSOES)
    async with _semaforo_sessoes:
        db = SessionLocal()
        try:
            yield db
        finally:
            await run_in_threadpool(db.close)
