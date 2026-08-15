from fastapi import FastAPI, BackgroundTasks, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from app.core.database import engine, Base, get_db
from app.api.v1 import turnos, dashboard, maquinas, predictions
from app.schemas.turno_schema import FechamentoTurnoCreate
from app.models.registro_turno import Turno, RegistroHorario, Maquina
from app.services.analytics import calcular_kpis_turno
from app.services.pdf_generator import gerar_relatorio_turno_pdf
from app.services.mailer import enviar_relatorio_email

# Criação automática de tabelas no PostgreSQL (caso não existam)
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="SIAMP API",
    description="Sistema Integrado de Apontamento, Machine Learning e Gestão de Produção",
    version="1.0.0"
)

# Configuração de CORS para permitir acesso local e via rede industrial
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Registro das rotas da API
app.include_router(maquinas.router, prefix="/api/v1")
app.include_router(turnos.router, prefix="/api/v1")
app.include_router(dashboard.router, prefix="/api/v1")
app.include_router(predictions.router, prefix="/api/v1")

# Endpoint Completo de Fechamento de Turno com Disparo de Relatório em Background
@app.post("/turnos/fechamento", status_code=201)
def processar_fechamento_turno(
    dados: FechamentoTurnoCreate, 
    background_tasks: BackgroundTasks, 
    db: Session = Depends(get_db)
):
    try:
        # 1. Persiste o cabeçalho do Turno
        novo_turno = Turno(
            nome_turno=dados.nome_turno,
            responsavel_nome=dados.responsavel_nome,
            observacoes=dados.observacoes,
            status_assinatura="ASSINADO_DIGITALMENTE"
        )
        db.add(novo_turno)
        db.flush()

        # 2. Persiste os registros horários de cada máquina
        for reg in dados.registros:
            registro_db = RegistroHorario(
                turno_id=novo_turno.id,
                maquina_id=reg.maquina_id,
                hora_referencia=reg.hora_referencia,
                prod_executada=reg.prod_executada,
                inicio_parada=reg.inicio_parada,
                retomada=reg.retomada,
                motivo_parada=reg.motivo_parada
            )
            db.add(registro_db)

        db.commit()
        db.refresh(novo_turno)

        # 3. Calcula KPIs e agenda a geração de PDF e envio de e-mail em background
        kpis = calcular_kpis_turno(db, novo_turno.id)
        
        dados_turno_dict = {
            "nome_turno": novo_turno.nome_turno,
            "responsavel_nome": novo_turno.responsavel_nome
        }
        
        pdf_bytes = gerar_relatorio_turno_pdf(dados_turno_dict, kpis)
        
        destinatarios = ["gerente.producao@empresa.com", "supervisao@empresa.com"]
        assunto = f"[SIAMP] Fechamento de Turno: {novo_turno.nome_turno}"
        corpo = f"<p>Segue em anexo o relatório diário de produção. OEE apurado: <b>{kpis['eficiencia_oee']}%</b>.</p>"

        background_tasks.add_task(enviar_relatorio_email, destinatarios, assunto, corpo, pdf_bytes)

        return {
            "status": "sucesso",
            "mensagem": "Turno encerrado e relatório agendado para envio!",
            "turno_id": novo_turno.id,
            "kpis": kpis
        }

    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Erro interno: {str(e)}")

@app.get("/")
def health_check():
    return {"status": "online", "sistema": "SIAMP v1.0.0"}