from sqlalchemy import Column, Integer, String, Float, ForeignKey, DateTime, Time, Text
from sqlalchemy.orm import relationship
from datetime import datetime
from app.core.database import Base

class Maquina(Base):
    __tablename__ = "maquinas"

    id = Column(Integer, primary_key=True, index=True)
    numero_maquina = Column(Integer, nullable=False, unique=True) # Ex: 1 a 6
    descricao = Column(String(100), nullable=False)
    cavidades = Column(Integer, default=1)
    ciclo_padrao = Column(Float, nullable=False) # em segundos

    registros = relationship("RegistroHorario", back_populates="maquina")


class Turno(Base):
    __tablename__ = "turnos"

    id = Column(Integer, primary_key=True, index=True)
    nome_turno = Column(String(50), nullable=False) # Ex: '1º Turno (05:00 - 13:00)'
    data_registro = Column(DateTime, default=datetime.utcnow)
    responsavel_nome = Column(String(120), nullable=False)
    observacoes = Column(Text, nullable=True)
    status_assinatura = Column(String(20), default="PENDENTE")

    registros = relationship("RegistroHorario", back_populates="turno")


class RegistroHorario(Base):
    __tablename__ = "registros_horarios"

    id = Column(Integer, primary_key=True, index=True)
    turno_id = Column(Integer, ForeignKey("turnos.id"), nullable=False)
    maquina_id = Column(Integer, ForeignKey("maquinas.id"), nullable=False)
    hora_referencia = Column(String(5), nullable=False) # Ex: '05:00', '06:00'
    prod_executada = Column(Integer, default=0)
    inicio_parada = Column(Time, nullable=True)
    retomada = Column(Time, nullable=True)
    motivo_parada = Column(String(150), nullable=True)

    turno = relationship("Turno", back_populates="registros")
    maquina = relationship("Maquina", back_populates="registros")