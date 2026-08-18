import os
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+psycopg2://siamp_user:siamp_password@localhost:5432/siamp_db"
)

# pool_size/max_overflow são específicos do QueuePool (usado em Postgres) e
# quebram a criação da engine em SQLite (usado nos testes, que roda com
# SingletonThreadPool/StaticPool). Por isso só são aplicados fora do SQLite.
_eh_sqlite = DATABASE_URL.startswith("sqlite")

_engine_kwargs = {"pool_pre_ping": True}  # Testa a conexão antes de executar query (evita conexões mortas)
if not _eh_sqlite:
    _engine_kwargs["pool_size"] = 10       # Número de conexões persistentes no pool
    _engine_kwargs["max_overflow"] = 20    # Conexões extras permitidas em picos

# Pool de conexões otimizado para requisições concorrentes
engine = create_engine(DATABASE_URL, **_engine_kwargs)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

# Dependência do FastAPI para injetar a sessão do banco nas rotas
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()