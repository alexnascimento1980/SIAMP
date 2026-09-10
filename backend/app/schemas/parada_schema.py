from datetime import time

from pydantic import BaseModel, Field, model_validator


class ParadaCreate(BaseModel):
    turno_id: int = Field(..., gt=0)
    maquina_id: int = Field(..., gt=0)
    inicio: time
    fim: time | None = None
    duracao_minutos: float | None = Field(default=None, ge=0)
    motivo: str = Field(..., min_length=2, max_length=100)
    categoria: str | None = Field(default=None, max_length=50)
    observacao: str | None = Field(default=None, max_length=1000)

    # usuario_id NÃO é um campo aqui de propósito - quem registrou a
    # parada é sempre o usuário autenticado (resolvido no endpoint a
    # partir do token/cookie de sessão), nunca um valor informado pelo
    # cliente. Aceitar isso do payload permitiria qualquer usuário
    # autenticado atribuir uma parada a outra pessoa, corrompendo a
    # trilha de auditoria (achado numa avaliação de segurança do
    # projeto - antes existia como campo opcional, com o endpoint só
    # usando o valor do usuário autenticado como fallback quando o
    # cliente não enviava nada, mas confiando cegamente nele quando
    # enviado).

    @model_validator(mode="after")
    def validar_periodo(self):
        if self.fim is not None and self.fim < self.inicio:
            raise ValueError("fim não pode ser anterior ao início da parada.")
        return self
