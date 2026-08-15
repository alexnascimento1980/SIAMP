import pandas as pd
import numpy as np

def processar_features_producao(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    
    # 1. Capacidade teórica horária por máquina
    # Fórmula: (3600 segundos / ciclo_padrao) * cavidades
    df["capacidade_teorica_hora"] = ((3600 / df["ciclo_padrao"]) * df["cavidades"]).astype(int)
    
    # 2. Eficiência horária (%)
    df["eficiencia_hora"] = np.where(
        df["capacidade_teorica_hora"] > 0,
        (df["prod_executada"] / df["capacidade_teorica_hora"]) * 100,
        0.0
    )
    
    # 3. Tratamento de paradas e preenchimento de nulos
    df["tempo_parada_minutos"] = df["tempo_parada_minutos"].fillna(0)
    df["teve_parada"] = (df["tempo_parada_minutos"] > 0).astype(int)
    
    # 4. Variável Alvo (Target): 1 se houve desvio crítico (<70% de eficiência ou >20min de parada), 0 se normal
    df["alerta_critico"] = np.where(
        (df["eficiencia_hora"] < 70) | (df["tempo_parada_minutos"] > 20),
        1,
        0
    )
    
    return df