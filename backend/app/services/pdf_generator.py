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
        cabecalho_detalhe = ["Hora", "Máquina", "Peça", "Produção", "Esperado", "Parada"]
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
                reg.get("produto_descricao") or "-",
                str(reg["prod_executada"]),
                str(reg.get("producao_esperada", "-")),
                parada_txt,
            ])

        tabela_detalhe = Table(
            linhas_detalhe, colWidths=[40, 45, 190, 55, 55, 135], repeatRows=1
        )
        tabela_detalhe.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#F3F4F6')),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 8),
            ('ALIGN', (0, 0), (0, -1), 'CENTER'),
            ('ALIGN', (3, 0), (4, -1), 'CENTER'),
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