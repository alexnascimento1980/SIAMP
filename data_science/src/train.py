import joblib
import os
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report
from src.data_loader import carregar_dados_producao
from src.feature_engineering import processar_features_producao, FEATURES


def treinar_modelo():
    print("🔄 Carregando lançamentos de turnos fechados...")
    df_raw = carregar_dados_producao()

    if df_raw.empty or len(df_raw) < 30:
        print(
            "⚠️  Poucos lançamentos no banco para treinar. Rode "
            "'python -m src.synthetic_data_generator' para gerar um "
            "histórico sintético, ou aguarde mais produção real ser "
            "registrada."
        )
        return

    df = processar_features_producao(df_raw)
    if len(df) < 20:
        print(
            "⚠️  Poucas linhas após o processamento de features - o "
            "modelo precisa de sequências de lançamentos por máquina "
            "(cada lançamento de produção precisa ter um lançamento "
            "seguinte na mesma máquina para servir de alvo)."
        )
        return

    X = df[FEATURES]
    y = df["proximo_e_falha"]

    estratificar = y if y.nunique() > 1 else None
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=estratificar
    )

    modelo = RandomForestClassifier(
        n_estimators=150, max_depth=6, min_samples_leaf=5,
        random_state=42, class_weight="balanced",
    )
    modelo.fit(X_train, y_train)

    y_pred = modelo.predict(X_test)
    print("📊 Desempenho do modelo (previsão de próxima parada não programada):")
    print(classification_report(y_test, y_pred, zero_division=0))
    print("📈 Importância de cada feature:")
    for nome, importancia in sorted(
        zip(FEATURES, modelo.feature_importances_), key=lambda x: -x[1]
    ):
        print(f"   {nome}: {importancia:.3f}")

    # Salva DENTRO de backend/app/ml_models/ - os dois Dockerfiles do
    # projeto (backend/Dockerfile e deploy/Dockerfile) já copiam todo
    # o conteúdo de backend/ para a imagem, então o modelo passa a
    # estar disponível automaticamente em qualquer ambiente
    # containerizado, sem precisar de nenhuma linha de COPY adicional.
    # Antes, o modelo era salvo em data_science/models/ - uma pasta
    # fora do contexto de build dos dois Dockerfiles, e por isso nunca
    # era efetivamente carregada em produção nem no docker-compose
    # local, mesmo já tendo sido treinado.
    diretorio_saida = os.path.join(
        os.path.dirname(__file__), "..", "..", "backend", "app", "ml_models"
    )
    os.makedirs(diretorio_saida, exist_ok=True)
    caminho_modelo = os.path.join(diretorio_saida, "modelo_risco_parada.joblib")
    joblib.dump({"modelo": modelo, "features": FEATURES}, caminho_modelo)
    print(f"✅ Modelo salvo em: {os.path.abspath(caminho_modelo)}")


if __name__ == "__main__":
    treinar_modelo()
