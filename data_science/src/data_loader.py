import os
import pandas as pd
from sqlalchemy import create_engine

# Remove the global DB_URL and get_engine() function if they are causing issues

def carregar_dados_producao(db_url: str = None) -> pd.DataFrame:
    """Extrai todos os registros de produção consolidados com máquinas e turnos."""
    
    # If no URL is provided, try to get it from the environment, otherwise use the default
    if db_url is None:
        db_url = os.getenv(
            "DATABASE_URL",
            "postgresql+psycopg2://siamp_user:siamp_password@localhost:5432/siamp_db"
        )
        
    query = """
        SELECT 
            r.id AS registro_id,
            t.id AS turno_id,
            t.data_registro,
            t.nome_turno,
            t.responsavel_nome,
            m.numero_maquina,
            m.descricao AS maquina_descricao,
            m.cavidades,
            m.ciclo_padrao,
            r.hora_referencia,
            r.prod_executada,
            r.inicio_parada,
            r.retomada,
            r.motivo_parada,
            CASE 
                WHEN r.inicio_parada IS NOT NULL AND r.retomada IS NOT NULL 
                THEN EXTRACT(EPOCH FROM (r.retomada - r.inicio_parada)) / 60
                ELSE 0 
            END AS tempo_parada_minutos
        FROM registros_horarios r
        JOIN turnos t ON r.turno_id = t.id
        JOIN maquinas m ON r.maquina_id = m.id
        ORDER BY t.data_registro DESC, r.hora_referencia ASC;
    """
    engine = create_engine(db_url)
    df = pd.read_sql(query, con=engine)
    return df