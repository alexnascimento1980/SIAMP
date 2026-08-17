import io
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

def gerar_relatorio_turno_pdf(dados_turno: dict, kpis: dict) -> bytes:
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
    dados_resumo = [
        ["Total Produzido (pçs)", "Produção Esperada", "Tempo de Parada Total", "Eficiência (OEE)"],
        [f"{kpis['total_produzido']}", f"{kpis['total_esperado']}", f"{kpis['minutos_parados']} min", f"{kpis['eficiencia_oee']}%"]
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
    elementos.append(Spacer(1, 10))

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

    # Súmula da IA
    alerta_style = ParagraphStyle('Alerta', parent=styles['Normal'], textColor=colors.HexColor('#B91C1C') if kpis['eficiencia_oee'] < 75 else colors.HexColor('#15803D'))
    elementos.append(Paragraph(f"<b>Diagnóstico de Inteligência:</b> {kpis['alerta_ia']}", alerta_style))
    
    doc.build(elementos)
    buffer.seek(0)
    return buffer.getvalue()