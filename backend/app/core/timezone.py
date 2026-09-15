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

from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

FUSO_BRASILIA = ZoneInfo("America/Sao_Paulo")


def agora_brasilia() -> datetime:
    """Data/hora atual no fuso de Brasília, como datetime "naive" (sem
    tzinfo) - consistente com as colunas DateTime (sem timezone) já
    usadas no banco, que armazenam o valor exatamente como recebido,
    sem nenhuma conversão adicional na leitura."""
    return datetime.now(FUSO_BRASILIA).replace(tzinfo=None)


# A partir de qual hora um horário de início registrado é considerado
# "da noite anterior" (para fins de calcular_data_registro_turno) -
# cobre o 3º Turno (22:00-04:00, o único que atravessa a meia-noite
# entre os três turnos fixos hoje), com folga suficiente para não
# confundir com o 2º Turno (14:00-21:00) em nenhum cenário razoável.
_HORA_INICIO_CONSIDERADO_NOITE = 18
# Até qual hora do dia seguinte um fechamento/salvamento ainda é
# considerado "madrugada" (ainda pertencente ao turno da noite
# anterior) - cobre o horário de término do 3º Turno (04:00) com
# folga generosa para fechamentos atrasados, sem invadir o horário de
# início do 1º Turno (05:00).
_HORA_LIMITE_MADRUGADA = 5


def calcular_data_registro_turno(horarios_inicio: list[time]) -> datetime:
    """Data/hora a gravar como Turno.data_registro, corrigindo o caso
    de um turno que atravessa a meia-noite (ex.: 3º Turno, 22:00-04:00)
    - salvar ou fechar de madrugada não deve gravar a data de HOJE,
    mesmo sendo literalmente "agora": o turno começou ONTEM à noite,
    e é essa a data que deve aparecer no histórico, no dashboard e nos
    filtros por período (achado real relatado pelo usuário: um
    fechamento às 04h aparecia com a data do dia do fechamento, não a
    do dia em que o turno realmente começou).

    Recebe o horário de início de cada lançamento/registro já sendo
    salvo (não o nome do turno escolhido no formulário) - mais robusto
    que casar por texto ("3º Turno..."), e funciona mesmo que os
    horários dos turnos mudem no futuro: usa o sinal real (horário
    mais cedo já registrado) em vez de um texto fixo.

    Regra: se ALGUM horário registrado for "de noite" (>= 18h) e o
    momento atual for "de madrugada" (< 5h), a data recua um dia. Usa
    "algum é de noite" em vez de "o mais cedo é de noite" de propósito
    - min() comparando objetos time ignora em qual dia cada um
    aconteceu de verdade: numa lista como [22:00, 23:00, 02:00] (turno
    que já passou da meia-noite), min() dá 02:00 (menor no relógio de
    24h), não 22:00 (o que realmente aconteceu primeiro) - descartaria
    exatamente o sinal que essa função precisa enxergar."""
    agora = agora_brasilia()
    if not horarios_inicio:
        return agora

    algum_horario_e_noite = any(h.hour >= _HORA_INICIO_CONSIDERADO_NOITE for h in horarios_inicio)
    se_atravessou_meia_noite = algum_horario_e_noite and agora.hour < _HORA_LIMITE_MADRUGADA
    if se_atravessou_meia_noite:
        return agora - timedelta(days=1)
    return agora
