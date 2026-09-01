import os

import joblib
import pandas as pd
from sqlalchemy import func
from sqlalchemy.orm import Session

# Modelo salvo DENTRO de backend/ (não em data_science/models/, fora do
# contexto de build dos Dockerfiles) - garante que o artefato treinado
# seja incluído automaticamente em qualquer imagem Docker do projeto,
# local ou em produção. Ver data_science/src/train.py.
MODEL_PATH = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "ml_models", "modelo_risco_parada.joblib")
)

_modelo_cache = None


def carregar_modelo():
    global _modelo_cache
    if _modelo_cache is None and os.path.exists(MODEL_PATH):
        _modelo_cache = joblib.load(MODEL_PATH)
    return _modelo_cache


def _taxa_falha_historica(db: Session, coluna, valor) -> float:
    """Proporção de lançamentos do tipo PARADA_FALHA no histórico
    completo de uma máquina ou peça - mesma definição usada no treino
    (feature_engineering.py), só que ali calculada de forma expansiva
    (só o passado de cada linha) e aqui sobre todo o histórico
    disponível até agora, já que é isso que está disponível no
    momento da predição em produção. Turnos marcados como teste são
    excluídos - não representam comportamento real da operação, e
    contaminariam a taxa histórica de forma artificial."""
    from app.models.lancamento import Lancamento
    from app.models.turno import Turno

    if valor is None:
        return 0.0

    total = (
        db.query(func.count(Lancamento.id))
        .join(Turno, Lancamento.turno_id == Turno.id)
        .filter(coluna == valor, Turno.marcado_teste.is_(False))
        .scalar()
        or 0
    )
    if total == 0:
        return 0.0
    falhas = (
        db.query(func.count(Lancamento.id))
        .join(Turno, Lancamento.turno_id == Turno.id)
        .filter(coluna == valor, Lancamento.tipo == "PARADA_FALHA", Turno.marcado_teste.is_(False))
        .scalar()
        or 0
    )
    return falhas / total


def prever_risco_parada(
    db: Session,
    maquina_id: int,
    produto_id: int | None,
    ciclo_efetivo: float | None,
    ciclo_padrao_peca: float | None,
    cavidades_efetivas: int | None,
    duracao_min: float,
    quantidade: int | None,
    turno_num: int,
    dia_semana: int,
) -> dict:
    """Estima o risco de o PRÓXIMO lançamento desta máquina ser uma
    parada não programada - previsão voltada para a frente no tempo,
    diferente da versão anterior deste serviço, que apenas reafirmava
    uma regra sobre o próprio registro já observado (eficiência baixa
    ou parada longa), sem nenhum valor preditivo real: o dado já
    estava disponível no próprio dashboard.

    Combina o histórico de falha da máquina e da peça (quanto mais
    uma injetora ou um molde historicamente falha, maior o peso) com
    a divergência entre o ciclo real informado e o ciclo padrão
    cadastrado na peça (sinal de que o molde pode estar regulado
    diferente do esperado) e o desempenho do lançamento atual.
    """
    from app.models.lancamento import Lancamento

    if ciclo_padrao_peca and ciclo_padrao_peca > 0 and ciclo_efetivo:
        ciclo_divergencia_pct = (ciclo_efetivo - ciclo_padrao_peca) / ciclo_padrao_peca
    else:
        ciclo_divergencia_pct = 0.0

    if ciclo_efetivo and cavidades_efetivas and ciclo_efetivo > 0:
        capacidade_esperada = (duracao_min * 60 / ciclo_efetivo) * cavidades_efetivas
        desempenho_pct = min(3.0, (quantidade or 0) / capacidade_esperada) if capacidade_esperada > 0 else 1.0
    else:
        desempenho_pct = 1.0

    taxa_falha_maquina = _taxa_falha_historica(db, Lancamento.maquina_id, maquina_id)
    taxa_falha_peca = _taxa_falha_historica(db, Lancamento.produto_id, produto_id)

    modelo_info = carregar_modelo()

    if modelo_info is not None:
        modelo = modelo_info["modelo"]
        colunas = modelo_info["features"]
        features_dict = {
            "ciclo_divergencia_pct": ciclo_divergencia_pct,
            "desempenho_pct": desempenho_pct,
            "duracao_min": duracao_min,
            "taxa_falha_historica_maquina": taxa_falha_maquina,
            "taxa_falha_historica_peca": taxa_falha_peca,
            "turno_num": turno_num,
            "dia_semana": dia_semana,
        }
        df_input = pd.DataFrame([features_dict])[colunas]
        risco = int(modelo.predict(df_input)[0])
        probabilidade = float(modelo.predict_proba(df_input)[0][1])
        fonte = "modelo_ml"
    else:
        # Heurística de fallback (usada quando o .joblib ainda não foi
        # treinado/gerado) - combina os mesmos três sinais que o
        # modelo treinado usaria, com pesos simples e explicáveis, em
        # vez de reafirmar uma regra sobre o próprio dado já visível
        # no dashboard.
        pontuacao = (
            max(0.0, ciclo_divergencia_pct) * 0.4
            + taxa_falha_maquina * 0.4
            + taxa_falha_peca * 0.2
        )
        risco = 1 if pontuacao > 0.15 else 0
        probabilidade = min(0.95, pontuacao + 0.1)
        fonte = "heuristica"

    mensagem = (
        "Risco elevado de parada não programada na próxima produção desta injetora"
        if risco
        else "Sem sinais de risco elevado para a próxima produção desta injetora"
    )

    return {
        "risco_desvio": bool(risco),
        "probabilidade_critica": round(probabilidade * 100, 1),
        "mensagem": mensagem,
        "fonte": fonte,
        "detalhe": {
            "ciclo_divergencia_pct": round(ciclo_divergencia_pct * 100, 1),
            "taxa_falha_historica_maquina": round(taxa_falha_maquina * 100, 1),
            "taxa_falha_historica_peca": round(taxa_falha_peca * 100, 1),
        },
    }
