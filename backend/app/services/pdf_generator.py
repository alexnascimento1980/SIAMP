import io
from xml.sax.saxutils import escape as _escapar_xml

import matplotlib
matplotlib.use("Agg")  # sem display disponível no servidor - precisa vir antes de importar pyplot
import matplotlib.pyplot as plt

from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

# Cores da marca SIAMP (mesmas do frontend - ver frontend/css/styles.css)
_AZUL_MARINHO = "#004380"
_AZUL_CLARO = "#00ABE9"


def _gerar_grafico_barras(labels: list[str], valores: list[float], titulo: str) -> bytes:
    """Gráfico de barras simples (ex.: produção por injetora), como
    imagem PNG - para embutir no PDF via reportlab.platypus.Image.
    Usado no lugar de renderizar a própria página do dashboard num
    navegador headless: bem mais leve para rodar em background numa
    hospedagem com pouca memória (plano gratuito do Render)."""
    fig, ax = plt.subplots(figsize=(6.5, 3), dpi=150)
    ax.bar(labels, valores, color=_AZUL_MARINHO)
    ax.set_title(titulo, fontsize=11, color="#333333")
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.tick_params(axis="x", labelrotation=0, labelsize=8)
    fig.tight_layout()

    buffer = io.BytesIO()
    fig.savefig(buffer, format="png")
    plt.close(fig)
    buffer.seek(0)
    return buffer.getvalue()


def _gerar_grafico_producao_por_turno(labels: list[str], produzido: list[float], oee: list[float]) -> bytes:
    """Gráfico combinado barra (produção) + linha (OEE, eixo secundário)
    dos últimos turnos - mesmo formato do gráfico 'Produção por Turno'
    do dashboard na tela."""
    fig, ax1 = plt.subplots(figsize=(6.5, 3), dpi=150)
    ax1.bar(labels, produzido, color=_AZUL_MARINHO, label="Produção (pçs)")
    ax1.set_ylabel("Peças", fontsize=8)
    ax1.tick_params(axis="x", labelrotation=30, labelsize=7)
    ax1.spines["top"].set_visible(False)

    ax2 = ax1.twinx()
    ax2.plot(labels, oee, color=_AZUL_CLARO, marker="o", linewidth=2, label="OEE (%)")
    ax2.set_ylabel("OEE %", fontsize=8)
    ax2.set_ylim(0, max(100, max(oee) * 1.1 if oee else 100))

    ax1.set_title("Produção por Turno (últimos 10)", fontsize=11, color="#333333")
    linhas1, rotulos1 = ax1.get_legend_handles_labels()
    linhas2, rotulos2 = ax2.get_legend_handles_labels()
    ax1.legend(linhas1 + linhas2, rotulos1 + rotulos2, fontsize=7, loc="upper left")
    fig.tight_layout()

    buffer = io.BytesIO()
    fig.savefig(buffer, format="png")
    plt.close(fig)
    buffer.seek(0)
    return buffer.getvalue()


def _imagem_de_bytes(conteudo_png: bytes, largura_pt: float = 470) -> Image:
    """Monta um flowable Image do reportlab a partir de PNG em memória,
    preservando a proporção original da figura."""
    buffer = io.BytesIO(conteudo_png)
    img = Image(buffer)
    proporcao = img.imageHeight / img.imageWidth
    img.drawWidth = largura_pt
    img.drawHeight = largura_pt * proporcao
    return img


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
        # Células de texto mais longo (peça + ciclo usado, motivo de
        # parada) usam Paragraph em vez de string simples - string pura
        # não quebra linha dentro da largura da coluna, só transborda
        # por cima das colunas vizinhas.
        estilo_celula = ParagraphStyle('Celula', fontSize=7.5, leading=9)
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
                Paragraph(reg.get("produto_descricao") or "-", estilo_celula),
                str(reg["prod_executada"]),
                str(reg.get("producao_esperada", "-")),
                Paragraph(parada_txt, estilo_celula),
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
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
            ('TOPPADDING', (0, 0), (-1, -1), 4),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ]))
        elementos.append(tabela_detalhe)
        elementos.append(Spacer(1, 15))

    # Observações Gerais do turno, digitadas pelo responsável no
    # apontamento - texto livre, omitido do relatório se vazio (não
    # exibe uma seção vazia só por existir o campo). Escapa marcação
    # (<, >, &) antes de inserir no Paragraph - texto digitado pelo
    # usuário não é HTML seguro, e o ReportLab interpreta um
    # mini-HTML nesse componente; sem o escape, um caractere comum
    # como "<" (ex.: "Ciclo < 15s") quebraria a geração do PDF
    # inteiro, não só essa seção. Quebras de linha digitadas na
    # textarea viram <br/> depois do escape, para serem preservadas
    # (Paragraph não trata "\n" como quebra de linha por padrão).
    observacoes_turno = (dados_turno.get("observacoes") or "").strip()
    if observacoes_turno:
        texto_seguro = _escapar_xml(observacoes_turno).replace("\n", "<br/>")
        elementos.append(Paragraph("<b>Observações Gerais do Turno:</b>", styles['Normal']))
        elementos.append(Paragraph(texto_seguro, styles['Normal']))
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
    producao_por_turno: dict | None = None,
) -> bytes:
    """PDF complementar ao relatório de fechamento de turno: mostra o
    desempenho do próprio turno lado a lado com o acumulado diário,
    semanal e mensal, com os mesmos gráficos disponíveis na tela do
    dashboard (produção por injetora, produção por turno) - não só
    tabelas de números.

    metricas_por_periodo: {"diario": {...}, "semanal": {...}, "mensal": {...}},
    cada um no formato retornado por
    app.services.dashboard_service.calcular_metricas_acumuladas.
    producao_por_turno: formato de
    app.services.dashboard_service.montar_producao_por_turno - se não
    informado, esse gráfico é omitido.
    """
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=30, leftMargin=30, topMargin=30, bottomMargin=30)
    styles = getSampleStyleSheet()
    elementos = []

    titulo_style = ParagraphStyle('Titulo', parent=styles['Heading1'], fontSize=16, leading=20, textColor=colors.HexColor(_AZUL_MARINHO))
    subtitulo_style = ParagraphStyle('Subtitulo', parent=styles['Heading2'], fontSize=12, textColor=colors.HexColor(_AZUL_MARINHO))

    elementos.append(Paragraph("SIAMP - Dashboard do Fechamento de Turno", titulo_style))
    elementos.append(Paragraph(
        f"<b>Turno:</b> {dados_turno['nome_turno']} | <b>Responsável:</b> {dados_turno['responsavel_nome']}",
        styles['Normal'],
    ))
    elementos.append(Spacer(1, 15))

    # Desempenho do próprio turno - mesmo dado do relatório de
    # fechamento, repetido aqui como ponto de referência para comparar
    # com o acumulado logo abaixo.
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
    # o diário/semanal isoladamente. Mesmo gráfico de barras do
    # dashboard na tela, não uma tabela.
    producao_maquina = metricas_por_periodo["mensal"].get("producao_por_maquina", [])
    if producao_maquina:
        elementos.append(Paragraph("Produção por Injetora - Últimos 30 dias", subtitulo_style))
        labels_maquina = [f"Injetora {m['numero_maquina']}" for m in producao_maquina]
        valores_maquina = [m["total_produzido"] for m in producao_maquina]
        grafico_maquina = _gerar_grafico_barras(labels_maquina, valores_maquina, "")
        elementos.append(_imagem_de_bytes(grafico_maquina))
        elementos.append(Spacer(1, 10))

    # Produção por turno (últimos 10) - mesmo gráfico combinado
    # barra+linha (produção x OEE) da tela do dashboard.
    if producao_por_turno and producao_por_turno.get("labels"):
        elementos.append(Paragraph("Produção por Turno (últimos 10)", subtitulo_style))
        grafico_turno = _gerar_grafico_producao_por_turno(
            producao_por_turno["labels"],
            producao_por_turno["produzido"],
            producao_por_turno["oee"],
        )
        elementos.append(_imagem_de_bytes(grafico_turno))

    doc.build(elementos)
    buffer.seek(0)
    return buffer.getvalue()