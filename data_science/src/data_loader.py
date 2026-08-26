import os
import pandas as pd
from sqlalchemy import create_engine


def carregar_dados_producao(db_url: str = None) -> pd.DataFrame:
    """Extrai todos os lançamentos de turnos fechados, com os dados de
    máquina e peça necessários para o cálculo de features - modelo
    ATUAL de apontamento (Lancamento/lancamentos_turno), não mais o
    modelo antigo por hora (RegistroHorario), que não recebe novos
    dados desde a introdução do modelo de lançamentos livres."""
    if db_url is None:
        db_url = os.getenv(
            "DATABASE_URL",
            "postgresql+psycopg2://siamp_user:siamp_password@localhost:5432/siamp_db",
        )

    query = """
        SELECT
            l.id AS lancamento_id,
            l.turno_id,
            t.data_registro,
            t.nome_turno,
            m.id AS maquina_id,
            m.numero_maquina,
            m.cavidades AS cavidades_maquina,
            m.ciclo_padrao AS ciclo_padrao_maquina,
            l.tipo,
            l.horario_inicio,
            l.horario_fim,
            l.produto_id,
            l.quantidade,
            l.ciclo_informado,
            p.cavidades AS cavidades_peca,
            p.ciclo_padrao AS ciclo_padrao_peca
        FROM lancamentos_turno l
        JOIN turnos t ON l.turno_id = t.id
        JOIN maquinas m ON l.maquina_id = m.id
        LEFT JOIN produtos p ON l.produto_id = p.id
        WHERE t.status_assinatura = 'ASSINADO_DIGITALMENTE'
        ORDER BY m.numero_maquina, t.data_registro, l.horario_inicio
    """
    engine = create_engine(db_url)
    df = pd.read_sql(query, con=engine)
    return df
