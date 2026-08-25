import io
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

def gerar_relatorio_turno_pdf(dados_turno: dict, kpis: dict, registros: list[dict] | None = None) -> bytes:
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=30, leftMargin=30, topMargin=30, bottomMargin=30)
    styles = getSampleStyleSheet()
    elementos = []

    # Cabeçalho
    titulo_style = ParagraphStyle('Titulo', parent=styles['Heading1'], fontSize=16, leading=20, textColor=colors.HexColor('#1E3A8A'))
    elementos.append(Paragraph(f"SIAMP - Relatório de Fechamento de Turno", titulo_style))
    elementos.append(Paragraph(f"<b>Turno:</b> {dados_turno['nome_turno']} | <b>Responsável:</b> {dados_turno['responsavel_nome']}", styles['Normal']))
    elementos.append(Spacer(1, 15))

    # Tabela de KPIs Principais (Produção)
    minutos_programados = kpis.get('minutos_parados_programados', 0)
    minutos_nao_programados = kpis.get(
        'minutos_parados_nao_programados', kpis['minutos_parados']
    )
    dados_resumo = [
        ["Total Produzido (pçs)", "Produção Esperada", "Parada Não Programada", "Eficiência (OEE)"],
        [f"{kpis['total_produzido']}", f"{kpis['total_esperado']}", f"{minutos_nao_programados} min", f"{kpis['eficiencia_oee']}%"]
    ]
    tabela = Table(dados_resumo, colWidths=[130, 130, 130, 130])
    tabela.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#F3F4F6')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.black),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
    ]))
    elementos.append(tabela)
    elementos.append(Spacer(1, 6))
    if minutos_programados:
        elementos.append(Paragraph(
            f"Parada programada (não penaliza o OEE): {minutos_programados} min",
            styles['Normal'],
        ))
        elementos.append(Spacer(1, 6))

    # Tabela de Qualidade (Índice de Produção × Índice de Qualidade = OEE)
    dados_qualidade = [
        ["Peças Boas", "Refugo", "Índice de Produção", "Índice de Qualidade"],
        [
            f"{kpis.get('total_pecas_boas', 0)}",
            f"{kpis.get('total_refugo', 0)}",
            f"{kpis.get('indice_producao', 0)}%",
            f"{kpis.get('indice_qualidade', 100)}%",
        ],
    ]
    tabela_qualidade = Table(dados_qualidade, colWidths=[130, 130, 130, 130])
    tabela_qualidade.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#F3F4F6')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.black),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
    ]))
    elementos.append(tabela_qualidade)
    elementos.append(Spacer(1, 15))

    # Detalhe por hora/máquina: qual peça foi produzida e o tipo de parada
    # (quando houve), para o relatório deixar isso explícito.
    if registros:
        cabecalho_detalhe = ["Hora", "Máquina", "OP", "Peça", "Produção", "Esperado", "Parada"]
        linhas_detalhe = [cabecalho_detalhe]
        for reg in registros:
            if reg.get("inicio_parada"):
                parada_txt = f"{reg['inicio_parada']}–{reg.get('retomada') or '?'}"
                parada_txt += " (programada)" if reg.get("parada_programada") else " (não programada)"
            else:
                parada_txt = "-"
            linhas_detalhe.append([
                reg["hora_referencia"],
                reg["numero_maquina"],
                reg.get("numero_op") or "-",
                reg.get("produto_descricao") or "-",
                str(reg["prod_executada"]),
                str(reg.get("producao_esperada", "-")),
                parada_txt,
            ])

        tabela_detalhe = Table(
            # "Hora" precisa caber tanto um horário único (modelo por
            # hora, "05:00") quanto um intervalo (modelo de lançamentos,
            # "22:00-05:00") - por isso mais larga que as demais colunas
            # estreitas eram originalmente dimensionadas só para o
            # formato antigo.
            linhas_detalhe, colWidths=[68, 42, 48, 148, 48, 48, 103], repeatRows=1
        )
        tabela_detalhe.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#F3F4F6')),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 8),
            ('ALIGN', (0, 0), (0, -1), 'CENTER'),
            ('ALIGN', (4, 0), (5, -1), 'CENTER'),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
            ('TOPPADDING', (0, 0), (-1, -1), 4),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ]))
        elementos.append(tabela_detalhe)
        elementos.append(Spacer(1, 15))

    # Súmula da IA
    alerta_style = ParagraphStyle('Alerta', parent=styles['Normal'], textColor=colors.HexColor('#B91C1C') if kpis['eficiencia_oee'] < 75 else colors.HexColor('#15803D'))
    elementos.append(Paragraph(f"<b>Diagnóstico de Inteligência:</b> {kpis['alerta_ia']}", alerta_style))
    
    doc.build(elementos)
    buffer.seek(0)
    return buffer.getvalue()


def gerar_relatorio_dashboard_pdf(
    dados_turno: dict,
    kpis_turno: dict,
    metricas_por_periodo: dict,
) -> bytes:
    """PDF complementar ao relatório de fechamento de turno: mostra o
    desempenho do próprio turno lado a lado com o acumulado diário,
    semanal e mensal - contexto que o relatório de fechamento sozinho
    não dá, já que ele só fala do turno isolado.

    metricas_por_periodo: {"diario": {...}, "semanal": {...}, "mensal": {...}},
    cada um no formato retornado por
    app.services.dashboard_service.calcular_metricas_acumuladas.
    """
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=30, leftMargin=30, topMargin=30, bottomMargin=30)
    styles = getSampleStyleSheet()
    elementos = []

    titulo_style = ParagraphStyle('Titulo', parent=styles['Heading1'], fontSize=16, leading=20, textColor=colors.HexColor('#1E3A8A'))
    elementos.append(Paragraph("SIAMP - Dashboard do Fechamento de Turno", titulo_style))
    elementos.append(Paragraph(
        f"<b>Turno:</b> {dados_turno['nome_turno']} | <b>Responsável:</b> {dados_turno['responsavel_nome']}",
        styles['Normal'],
    ))
    elementos.append(Spacer(1, 15))

    # Desempenho do próprio turno - mesmo dado do relatório de
    # fechamento, repetido aqui como ponto de referência para comparar
    # com o acumulado logo abaixo.
    subtitulo_style = ParagraphStyle('Subtitulo', parent=styles['Heading2'], fontSize=12, textColor=colors.HexColor('#1E3A8A'))
    elementos.append(Paragraph("Este turno", subtitulo_style))
    dados_turno_tabela = [
        ["Produzido (pçs)", "Esperado (pçs)", "Eficiência (OEE)"],
        [f"{kpis_turno['total_produzido']}", f"{kpis_turno['total_esperado']}", f"{kpis_turno['eficiencia_oee']}%"],
    ]
    tabela_turno = Table(dados_turno_tabela, colWidths=[170, 170, 170])
    tabela_turno.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#F3F4F6')),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
    ]))
    elementos.append(tabela_turno)
    elementos.append(Spacer(1, 18))

    # Acumulado diário/semanal/mensal, lado a lado numa tabela só -
    # facilita ver se este turno está puxando a média pra cima ou pra
    # baixo do que vem sendo o padrão recente.
    elementos.append(Paragraph("Acumulado (turnos fechados)", subtitulo_style))
    rotulos_periodo = {"diario": "Hoje", "semanal": "Últimos 7 dias", "mensal": "Últimos 30 dias"}
    linhas_acumulado = [["Período", "Turnos", "Produzido (pçs)", "OEE Médio"]]
    for chave in ("diario", "semanal", "mensal"):
        m = metricas_por_periodo[chave]
        linhas_acumulado.append([
            rotulos_periodo[chave],
            str(m["total_turnos_encerrados"]),
            f"{m['total_pecas_produzidas']}",
            f"{m['oee_medio_estimado']}%",
        ])
    tabela_acumulado = Table(linhas_acumulado, colWidths=[130, 100, 140, 140])
    tabela_acumulado.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#F3F4F6')),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
    ]))
    elementos.append(tabela_acumulado)
    elementos.append(Spacer(1, 18))

    # Produção por injetora no acumulado mensal - o período mais amplo
    # dos três, mais útil para enxergar padrão entre máquinas do que
    # o diário/semanal isoladamente.
    producao_maquina = metricas_por_periodo["mensal"].get("producao_por_maquina", [])
    if producao_maquina:
        elementos.append(Paragraph("Produção por Injetora - Últimos 30 dias", subtitulo_style))
        linhas_maquina = [["Injetora", "Produzido (pçs)"]]
        for m in producao_maquina:
            linhas_maquina.append([f"Injetora {m['numero_maquina']}", str(m["total_produzido"])])
        tabela_maquina = Table(linhas_maquina, colWidths=[250, 250])
        tabela_maquina.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#F3F4F6')),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ]))
        elementos.append(tabela_maquina)

    doc.build(elementos)
    buffer.seek(0)
    return buffer.getvalue()