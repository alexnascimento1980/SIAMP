import joblib
import os
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report
from src.data_loader import carregar_dados_producao
from src.feature_engineering import processar_features_producao

def treinar_modelo():
    print("🔄 Carregando dados do PostgreSQL...")
    df_raw = carregar_dados_producao()
    
    if df_raw.empty or len(df_raw) < 10:
        print("⚠️ Poucos registros no banco. Adicione mais dados para treinar.")
        return

    df = processar_features_producao(df_raw)
    
    # Seleção de Features preditivas
    features = ["numero_maquina", "cavidades", "ciclo_padrao", "tempo_parada_minutos", "capacidade_teorica_hora"]
    X = df[features]
    y = df["alerta_critico"]
    
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
    
    modelo = RandomForestClassifier(n_estimators=100, max_depth=5, random_state=42)
    modelo.fit(X_train, y_train)
    
    y_pred = modelo.predict(X_test)
    print("📊 Desempenho do Modelo:")
    print(classification_report(y_test, y_pred))
    
    # Salva o artefato treinado
    os.makedirs("models", exist_ok=True)
    caminho_modelo = "models/modelo_desvio_producao.joblib"
    joblib.dump(modelo, caminho_modelo)
    print(f"✅ Modelo salvo com sucesso em: {caminho_modelo}")

if __name__ == "__main__":
    treinar_modelo()