import numpy as np
import pandas as pd

# Mesma lista usada no treino (train.py) e na predição em produção
# (backend/app/services/ml_engine.py) - qualquer mudança aqui precisa
# ser replicada nos dois lugares, ou o modelo treinado passa a
# receber colunas em ordem/formato diferente do esperado.
FEATURES = [
    "ciclo_divergencia_pct",
    "desempenho_pct",
    "duracao_min",
    "taxa_falha_historica_maquina",
    "taxa_falha_historica_peca",
    "turno_num",
    "dia_semana",
]


def _duracao_minutos(inicio, fim) -> float:
    """Duração em minutos entre dois horários, tratando virada de
    meia-noite (fim <= início) somando 24h - mesma lógica usada no
    cálculo de OEE (app/services/analytics.py:_duracao_segundos).

    Aceita tanto datetime.time quanto string 'HH:MM:SS' - o driver do
    Postgres (psycopg2, usado em produção) devolve datetime.time para
    colunas TIME, mas o driver do SQLite (útil para testar o pipeline
    localmente sem precisar de um Postgres) devolve string."""
    def _para_segundos(valor) -> int:
        if isinstance(valor, str):
            partes = valor.split(":")
            h, m = int(partes[0]), int(partes[1])
            s = int(float(partes[2])) if len(partes) > 2 else 0
        else:
            h, m, s = valor.hour, valor.minute, valor.second
        return h * 3600 + m * 60 + s

    inicio_seg = _para_segundos(inicio)
    fim_seg = _para_segundos(fim)
    if fim_seg <= inicio_seg:
        fim_seg += 24 * 3600
    return (fim_seg - inicio_seg) / 60


def processar_features_producao(df: pd.DataFrame) -> pd.DataFrame:
    """Constrói features e o alvo (proximo_e_falha) a partir dos
    lançamentos, em ordem cronológica por máquina.

    O alvo olha para A FRENTE no tempo: se o PRÓXIMO lançamento desta
    mesma máquina é uma parada por falha não programada. Isso é
    diferente (e propositalmente mais útil) do que a versão anterior
    deste pipeline fazia - rotular o próprio registro sendo
    classificado com uma regra (eficiência baixa OU parada longa),
    que é a mesma regra usada como fallback quando o modelo não está
    disponível. Prever a MESMA janela que já está sendo observada não
    agrega valor preditivo algum; prever a PRÓXIMA parada, a partir de
    sinais disponíveis até agora, é uma previsão de verdade.

    As features, em contrapartida, só usam informação disponível até
    o momento deste lançamento (taxas históricas expansivas, câmera
    voltada só para trás) - evita vazamento de dados entre as
    features e o alvo.
    """
    df = df.copy()
    df = df.sort_values(["maquina_id", "data_registro", "horario_inicio"]).reset_index(drop=True)

    df["duracao_min"] = df.apply(
        lambda r: _duracao_minutos(r["horario_inicio"], r["horario_fim"]), axis=1
    )
    df["e_falha"] = (df["tipo"] == "PARADA_FALHA").astype(int)
    df["e_producao"] = (df["tipo"] == "PRODUCAO").astype(int)

    # Ciclo efetivo: informado manualmente > padrão da peça > padrão
    # da máquina - mesma prioridade usada no cálculo de OEE.
    df["ciclo_efetivo"] = df["ciclo_informado"]
    df["ciclo_efetivo"] = df["ciclo_efetivo"].fillna(df["ciclo_padrao_peca"])
    df["ciclo_efetivo"] = df["ciclo_efetivo"].fillna(df["ciclo_padrao_maquina"])
    df["cavidades_efetivas"] = df["cavidades_peca"].fillna(df["cavidades_maquina"])

    # Divergência do ciclo real em relação ao padrão cadastrado na
    # peça - sinal direto de que o molde pode estar regulado
    # diferente do esperado (mesmo conceito mostrado na tela de
    # apontamento, comparando os dois valores lado a lado).
    df["ciclo_divergencia_pct"] = np.where(
        (df["e_producao"] == 1) & df["ciclo_padrao_peca"].notna() & (df["ciclo_padrao_peca"] > 0),
        (df["ciclo_efetivo"] - df["ciclo_padrao_peca"]) / df["ciclo_padrao_peca"],
        0.0,
    )

    capacidade_esperada = np.where(
        (df["ciclo_efetivo"] > 0) & (df["cavidades_efetivas"] > 0),
        (df["duracao_min"] * 60 / df["ciclo_efetivo"].replace(0, np.nan)) * df["cavidades_efetivas"],
        np.nan,
    ).astype(float)
    capacidade_valida = np.nan_to_num(capacidade_esperada, nan=0.0) > 0
    df["desempenho_pct"] = np.where(
        (df["e_producao"] == 1) & capacidade_valida,
        df["quantidade"].fillna(0) / np.where(capacidade_valida, capacidade_esperada, 1),
        1.0,
    )
    df["desempenho_pct"] = df["desempenho_pct"].clip(0, 3)  # evita outlier extremo distorcer o modelo

    df["turno_num"] = df["nome_turno"].str.extract(r"(\d)º").astype(float).fillna(1).astype(int)
    df["dia_semana"] = pd.to_datetime(df["data_registro"]).dt.dayofweek

    # Taxas históricas EXPANSIVAS (olham só o passado até a linha
    # atual, exclusive, via shift(1)) - usar uma janela que inclui o
    # próprio futuro seria vazamento de dados entre features e alvo.
    df["taxa_falha_historica_maquina"] = (
        df.groupby("maquina_id")["e_falha"]
        .apply(lambda s: s.shift(1).expanding().mean())
        .reset_index(level=0, drop=True)
        .fillna(0.0)
    )
    df["taxa_falha_historica_peca"] = (
        df.groupby("produto_id")["e_falha"]
        .apply(lambda s: s.shift(1).expanding().mean())
        .reset_index(level=0, drop=True)
        .fillna(0.0)
    )

    # Alvo: o PRÓXIMO lançamento desta mesma máquina é uma falha não
    # programada?
    df["proximo_e_falha"] = df.groupby("maquina_id")["e_falha"].shift(-1)

    # Só lançamentos de produção fazem sentido como ponto de previsão
    # (é o momento em que o líder de turno quer saber o risco da
    # próxima parada) - e só os que já têm um "próximo" conhecido (o
    # último lançamento de cada máquina ainda não tem).
    df_features = df[(df["e_producao"] == 1) & df["proximo_e_falha"].notna()].copy()
    df_features["proximo_e_falha"] = df_features["proximo_e_falha"].astype(int)

    return df_features
