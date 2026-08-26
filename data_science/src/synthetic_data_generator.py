"""Gera um histórico sintético de turnos/lançamentos para treinar o
modelo de risco de parada não programada, quando não há (ou não há
ainda) volume suficiente de dados reais de produção.

Diferente da versão anterior deste script (que gerava dados no
modelo antigo por hora, RegistroHorario - hoje descontinuado como
fonte de novos apontamentos), este gera Lancamento, o modelo atual.

Simula viés realista intencional - algumas máquinas e algumas peças
têm taxa de falha mais alta que outras, e o ciclo real informado
diverge mais do padrão em alguns casos - para que o modelo tenha
sinal de verdade para aprender, em vez de dados puramente
aleatórios (que não ensinariam nada útil a um classificador).
"""

import random
from datetime import date, time, timedelta

from app.core.database import SessionLocal
from app.models.lancamento import Lancamento
from app.models.maquina import Maquina
from app.models.produto import Produto
from app.models.turno import Turno

TURNOS_CONFIG = [
    ("1º Turno (05:00 - 13:00)", 5, 13),
    ("2º Turno (13:00 - 21:00)", 13, 21),
    ("3º Turno (21:00 - 05:00)", 21, 5),  # atravessa a meia-noite
]

MOTIVOS_FALHA = [
    "Molde travado", "Sensor travado", "Queda de energia",
    "Falta de matéria-prima", "Bico entupido",
]


def _horario(hora_decimal: float) -> time:
    h = int(hora_decimal) % 24
    m = int((hora_decimal % 1) * 60)
    return time(h, m)


def popular_historico(dias: int = 90):
    db = SessionLocal()
    maquinas = db.query(Maquina).all()
    pecas = db.query(Produto).all()
    if not maquinas or not pecas:
        print("⚠️  Cadastre ao menos uma máquina e uma peça antes de gerar dados sintéticos.")
        return

    # Viés fixo por máquina (algumas injetoras mais problemáticas que
    # outras) e por peça (alguns moldes com ciclo menos estável) -
    # necessário para que taxa_falha_historica_maquina/peca tenham
    # correlação real com o alvo, em vez de ruído puro.
    risco_base_maquina = {m.id: random.uniform(0.03, 0.22) for m in maquinas}
    divergencia_base_peca = {p.id: random.uniform(0.0, 0.18) for p in pecas}

    data_base = date.today() - timedelta(days=dias)
    print(f"🔄 Gerando histórico sintético de {dias} dias, {len(maquinas)} máquina(s), {len(pecas)} peça(s)...")

    total_lancamentos = 0
    for d in range(dias):
        data_atual = data_base + timedelta(days=d)
        for nome_turno, hi, hf in TURNOS_CONFIG:
            turno = Turno(
                nome_turno=nome_turno,
                responsavel_nome=random.choice(["Alex Silva", "Carlos Souza", "Marcos Lima"]),
                observacoes="Registro sintético gerado para treino do modelo.",
                status_assinatura="ASSINADO_DIGITALMENTE",
                modelo_apontamento="LANCAMENTO",
                data_registro=data_atual,
            )
            db.add(turno)
            db.flush()

            duracao_turno_h = (hf - hi) % 24

            for maq in maquinas:
                peca = random.choice(pecas)
                risco_maquina = risco_base_maquina[maq.id]
                divergencia_peca = divergencia_base_peca[peca.id]

                cavidades = peca.cavidades or maq.cavidades or 2
                ciclo_padrao = peca.ciclo_padrao or maq.ciclo_padrao or 15.0

                cursor_h = float(hi)
                fim_turno_h = hi + duracao_turno_h

                while cursor_h < fim_turno_h - 0.2:
                    # Duração do lançamento de produção: entre 1h e 3h
                    duracao_h = min(random.uniform(1.0, 3.0), fim_turno_h - cursor_h)
                    inicio = _horario(cursor_h)
                    fim = _horario(cursor_h + duracao_h)

                    # Ciclo real diverge do padrão de acordo com o viés
                    # da peça, mais um ruído pequeno - simula molde
                    # regulado diferente do cadastrado.
                    divergencia = divergencia_peca + random.uniform(-0.03, 0.03)
                    ciclo_informado = round(ciclo_padrao * (1 + divergencia), 1)

                    duracao_seg = duracao_h * 3600
                    capacidade = (duracao_seg / ciclo_informado) * cavidades
                    quantidade = int(capacidade * random.uniform(0.85, 1.0))

                    db.add(Lancamento(
                        turno_id=turno.id, maquina_id=maq.id, tipo="PRODUCAO",
                        horario_inicio=inicio, horario_fim=fim,
                        produto_id=peca.id, quantidade=max(0, quantidade),
                        ciclo_informado=ciclo_informado,
                    ))
                    total_lancamentos += 1
                    cursor_h += duracao_h

                    # Chance de parada logo em seguida - maior quanto
                    # maior o risco da máquina e a divergência do ciclo,
                    # dando ao alvo (próximo lançamento é falha) sinal
                    # real correlacionado com as features.
                    prob_falha = min(0.6, risco_maquina + divergencia_peca * 0.5)
                    if cursor_h < fim_turno_h - 0.1 and random.random() < prob_falha:
                        dur_parada_h = random.uniform(0.1, 0.4)
                        inicio_p = _horario(cursor_h)
                        fim_p = _horario(cursor_h + dur_parada_h)
                        db.add(Lancamento(
                            turno_id=turno.id, maquina_id=maq.id, tipo="PARADA_FALHA",
                            horario_inicio=inicio_p, horario_fim=fim_p,
                            motivo=random.choice(MOTIVOS_FALHA),
                        ))
                        total_lancamentos += 1
                        cursor_h += dur_parada_h
                    elif cursor_h < fim_turno_h - 0.1 and random.random() < 0.08:
                        dur_parada_h = random.uniform(0.1, 0.3)
                        inicio_p = _horario(cursor_h)
                        fim_p = _horario(cursor_h + dur_parada_h)
                        db.add(Lancamento(
                            turno_id=turno.id, maquina_id=maq.id, tipo="PARADA_PROGRAMADA",
                            horario_inicio=inicio_p, horario_fim=fim_p,
                            motivo="Troca de molde",
                        ))
                        total_lancamentos += 1
                        cursor_h += dur_parada_h

        if d % 10 == 0:
            db.commit()

    db.commit()
    db.close()
    print(f"✅ Histórico sintético gerado: {total_lancamentos} lançamentos em {dias} dias.")


if __name__ == "__main__":
    popular_historico(90)
