"""Fuso horário padrão do sistema: Brasília (America/Sao_Paulo, UTC-3,
sem horário de verão desde 2019).

Usado no lugar de datetime.utcnow() e do server_default=func.now() do
SQLAlchemy (calculado pelo banco de dados) - ambos refletem o fuso do
servidor onde o processo roda, não necessariamente Brasília. Em
produção (Render + Supabase), esse servidor normalmente está
configurado em UTC, o que fazia toda data/hora gravada (fechamento de
turno, cadastro de usuário/peça/OP etc.) aparecer três horas à frente
do horário real de Brasília - é isso que este módulo corrige.
"""

from datetime import datetime
from zoneinfo import ZoneInfo

FUSO_BRASILIA = ZoneInfo("America/Sao_Paulo")


def agora_brasilia() -> datetime:
    """Data/hora atual no fuso de Brasília, como datetime "naive" (sem
    tzinfo) - consistente com as colunas DateTime (sem timezone) já
    usadas no banco, que armazenam o valor exatamente como recebido,
    sem nenhuma conversão adicional na leitura."""
    return datetime.now(FUSO_BRASILIA).replace(tzinfo=None)
