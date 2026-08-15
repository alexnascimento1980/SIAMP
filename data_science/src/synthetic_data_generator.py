import random
from datetime import datetime, timedelta
from app.core.database import SessionLocal
from app.models.registro_turno import Turno, RegistroHorario, Maquina

TURNOS_CONFIG = [
    ("1º Turno (05:00 - 13:00)", ["05:00", "06:00", "07:00", "08:00", "09:00", "10:00", "11:00", "12:00", "13:00"]),
    ("2º Turno (14:00 - 21:00)", ["14:00", "15:00", "16:00", "17:00", "18:00", "19:00", "20:00", "21:00"]),
    ("3º Turno (22:00 - 04:00)", ["22:00", "23:00", "00:00", "01:00", "02:00", "03:00", "04:00"])
]

MOTIVOS_PARADA = [
    "Molde travado", "Troca de matéria-prima", "Ajuste de temperatura",
    "Manutenção preventiva", "Queda de energia", "Limpeza de bico", "Falta de operador"
]

def popular_historico(dias: int = 90):
    db = SessionLocal()
    maquinas = db.query(Maquina).all()
    if not maquinas:
        print("⚠️ Execute as seeds de máquinas antes de gerar dados sintéticos.")
        return

    data_base = datetime.now() - timedelta(days=dias)
    print(f"🔄 Gerando histórico sintético de {dias} dias...")

    for d in range(dias):
        data_atual = data_base + timedelta(days=d)
        for nome_turno, horas in TURNOS_CONFIG:
            novo_turno = Turno(
                nome_turno=nome_turno,
                data_registro=data_atual,
                responsavel_nome=random.choice(["Alex Silva", "Carlos Souza", "Marcos Lima"]),
                observacoes="Registro automatizado de simulação.",
                status_assinatura="ASSINADO_DIGITALMENTE"
            )
            db.add(novo_turno)
            db.flush()

            for maq in maquinas:
                capacidade_nominal = int((3600 / maq.ciclo_padrao) * maq.cavidades)
                for hora in horas:
                    # 15% de chance de haver uma parada não programada
                    teve_parada = random.random() < 0.15
                    tempo_parada = random.randint(10, 45) if teve_parada else 0
                    motivo = random.choice(MOTIVOS_PARADA) if teve_parada else None
                    
                    fator_perda = (60 - tempo_parada) / 60
                    prod = int(capacidade_nominal * fator_perda * random.uniform(0.85, 1.0))

                    reg = RegistroHorario(
                        turno_id=novo_turno.id,
                        maquina_id=maq.id,
                        hora_referencia=hora,
                        prod_executada=max(0, prod),
                        motivo_parada=motivo
                    )
                    db.add(reg)

    db.commit()
    db.close()
    print("✅ Histórico de produção gerado com sucesso!")

if __name__ == "__main__":
    popular_historico(60)