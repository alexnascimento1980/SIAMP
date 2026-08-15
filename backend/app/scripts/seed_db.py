"""
Carrega database/seeds.sql no banco configurado em DATABASE_URL.
Idempotente: seeds.sql usa `ON CONFLICT DO NOTHING`.

Uso: python -m app.scripts.seed_db
"""
import os

from sqlalchemy import text

from app.core.database import engine

SEEDS_FILE = os.getenv("SEEDS_FILE", "/app/database/seeds.sql")


def main() -> None:
    if not os.path.exists(SEEDS_FILE):
        print(f"[seed_db] Arquivo de seed não encontrado em {SEEDS_FILE}; nada a fazer.")
        return

    with open(SEEDS_FILE, encoding="utf-8") as f:
        sql = f.read()

    with engine.begin() as conn:
        conn.execute(text(sql))

    print(f"[seed_db] Seeds aplicados a partir de {SEEDS_FILE}.")


if __name__ == "__main__":
    main()
