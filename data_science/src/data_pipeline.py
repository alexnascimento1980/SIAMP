import pandas as pd
from sqlalchemy import create_engine
import os

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+psycopg2://siamp_user:siamp_password@localhost:5432/siamp_db"
)

engine = create_engine(DATABASE_URL)

def carregar_dados_producao():
    query = """
        SELECT 
            r.id,
            t.data_registro,
            t.nome_turno,
            m.numero_maquina,
            m.cavidades,
            m.ciclo_padrao,
            r.hora_referencia,
            r.prod_executada,
            r.motivo_parada,
            EXTRACT(EPOCH FROM (r.retomada - r.inicio_parada))/60 AS tempo_parada_minutos
        FROM registros_horarios r
        JOIN turnos t ON r.turno_id = t.id
        JOIN maquinas m ON r.maquina_id = m.id;
    """
    df = pd.read_sql(query, con=engine)
    return df

# Exemplo de uso
# df = carregar_dados_producao()
# print(df.head())