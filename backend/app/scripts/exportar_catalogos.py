"""
Exporta os dados atuais das tabelas 'maquinas' e 'produtos' (peças) para
um arquivo .sql com INSERT ... ON CONFLICT DO NOTHING, no mesmo formato
de database/seeds.sql. Útil para levar customizações feitas localmente
(máquinas reais da fábrica, peças editadas/adicionadas) para outro
ambiente (ex.: Supabase em produção), em vez de depender só do seed
genérico.

Uso (rodar de dentro de backend/):

    # 1. Exporta do banco de ORIGEM (ex.: local via docker compose)
    $env:DATABASE_URL="postgresql+psycopg2://siamp_user:senha@localhost:5432/siamp_db"
    python -m app.scripts.exportar_catalogos

    # 2. Aplica no banco de DESTINO (ex.: Supabase), reaproveitando o
    #    seed_db.py já existente, só apontando para o arquivo exportado:
    $env:DATABASE_URL="<connection string do Supabase>"
    $env:SEEDS_FILE="../database/exportado_catalogos.sql"
    python -m app.scripts.seed_db

O arquivo gerado usa ON CONFLICT DO NOTHING, então é seguro rodar mais
de uma vez sem duplicar registros já existentes no destino.
"""
import os

from sqlalchemy.orm import Session

from app.core.database import engine
from app.models.maquina import Maquina
from app.models.produto import Produto

OUTPUT_FILE = os.getenv("EXPORT_FILE", "../database/exportado_catalogos.sql")


def _sql(valor) -> str:
    """Formata um valor Python como literal SQL, com escape correto de
    aspas simples em strings."""
    if valor is None:
        return "NULL"
    if isinstance(valor, bool):
        return "true" if valor else "false"
    if isinstance(valor, (int, float)):
        return str(valor)
    return "'" + str(valor).replace("'", "''") + "'"


def main() -> None:
    with Session(engine) as db:
        maquinas = db.query(Maquina).order_by(Maquina.numero_maquina).all()
        produtos = db.query(Produto).order_by(Produto.codigo).all()

    blocos = [
        "-- Gerado por `python -m app.scripts.exportar_catalogos`.",
        "-- Aplique com `seed_db.py` apontando SEEDS_FILE para este arquivo.",
        "",
    ]

    if maquinas:
        valores = ",\n".join(
            f"({_sql(m.numero_maquina)}, {_sql(m.descricao)}, {_sql(m.cavidades)}, "
            f"{_sql(m.ciclo_padrao)}, {_sql(m.ativo)})"
            for m in maquinas
        )
        blocos.append(
            "INSERT INTO maquinas (numero_maquina, descricao, cavidades, ciclo_padrao, ativo) VALUES\n"
            f"{valores}\nON CONFLICT (numero_maquina) DO NOTHING;\n"
        )

    if produtos:
        valores = ",\n".join(
            f"({_sql(p.codigo)}, {_sql(p.descricao)}, {_sql(p.ciclo_padrao)}, "
            f"{_sql(p.cavidades)}, {_sql(p.peso_gramas)}, {_sql(p.ativo)})"
            for p in produtos
        )
        blocos.append(
            "INSERT INTO produtos (codigo, descricao, ciclo_padrao, cavidades, peso_gramas, ativo) VALUES\n"
            f"{valores}\nON CONFLICT (codigo) DO NOTHING;\n"
        )

    if not maquinas and not produtos:
        print("[exportar_catalogos] Nenhuma máquina ou peça encontrada - nada para exportar.")
        return

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write("\n".join(blocos))

    print(
        f"[exportar_catalogos] {len(maquinas)} máquina(s) e {len(produtos)} "
        f"peça(s) exportadas para {OUTPUT_FILE}"
    )


if __name__ == "__main__":
    main()
