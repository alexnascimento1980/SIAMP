import os
import joblib
import pandas as pd

MODEL_PATH = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "../../../data_science/models/modelo_desvio_producao.joblib")
)

_modelo = None

def carregar_modelo():
    global _modelo
    if _modelo is None and os.path.exists(MODEL_PATH):
        _modelo = joblib.load(MODEL_PATH)
    return _modelo

def prever_risco_operacional(numero_maquina: int, cavidades: int, ciclo_padrao: float, tempo_parada_minutos: float) -> dict:
    modelo = carregar_modelo()
    capacidade_teorica = int((3600 / ciclo_padrao) * cavidades)

    # Se o modelo ainda não foi treinado, usa lógica heurística padrão
    if modelo is None:
        risco = 1 if tempo_parada_minutos > 20 else 0
        probabilidade = 0.85 if risco == 1 else 0.15
        fonte = "heuristica"
    else:
        df_input = pd.DataFrame([{
            "numero_maquina": numero_maquina,
            "cavidades": cavidades,
            "ciclo_padrao": ciclo_padrao,
            "tempo_parada_minutos": tempo_parada_minutos,
            "capacidade_teorica_hora": capacidade_teorica
        }])
        risco = int(modelo.predict(df_input)[0])
        probabilidade = float(modelo.predict_proba(df_input)[0][1])
        fonte = "modelo_ml"

    return {
        "risco_desvio": bool(risco),
        "probabilidade_critica": round(probabilidade * 100, 1),
        "mensagem": "Alerta de risco operacional iminente" if risco else "Operação com estabilidade estatística",
        # Indica se o diagnóstico veio do modelo scikit-learn treinado ou
        # da heurística de fallback (usada quando o .joblib ainda não
        # existe). O frontend usa isso para sinalizar a origem ao usuário.
        "fonte": fonte,
    }