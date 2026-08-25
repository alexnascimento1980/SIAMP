document.addEventListener("DOMContentLoaded", async () => {
  const sessao = await exigirSessao();
  if (!sessao) return;
  carregarDashboard();
});

async function carregarDashboard() {
  try {
    const res = await chamarApi("/dashboard/metricas-gerais");

    if (!res.ok) {
      throw new Error(`Falha ao carregar dashboard (HTTP ${res.status})`);
    }

    const dados = await res.json();

    // Atualiza KPIs
    document.getElementById("kpiProducao").innerText =
      dados.kpis.total_pecas_produzidas.toLocaleString("pt-BR") + " pçs";
    document.getElementById("kpiOEE").innerText =
      dados.kpis.oee_medio_estimado + "%";
    document.getElementById("kpiTurnos").innerText =
      dados.kpis.total_turnos_encerrados;

    // Atualiza Card de IA
    document.getElementById("iaMensagem").innerText = dados.insight_ml.mensagem;
    document.getElementById("iaProbTexto").innerText =
      `Probabilidade de desvio: ${dados.insight_ml.probabilidade_critica}%`;
    document.getElementById("iaBarraProbabilidade").style.width =
      dados.insight_ml.probabilidade_critica + "%";

    // Deixa claro se o diagnóstico veio do modelo scikit-learn treinado
    // ou da heurística de fallback (usada enquanto o modelo não existe).
    const fonteEl = document.getElementById("iaFonteTexto");
    if (dados.insight_ml.fonte === "modelo_ml") {
      fonteEl.innerHTML =
        '<i class="bi bi-cpu me-1"></i>Modelo de Machine Learning treinado, avaliando tempo de ciclo, cavidades e histórico de paradas.';
    } else {
      fonteEl.innerHTML =
        '<i class="bi bi-exclamation-triangle me-1"></i>Modelo ainda não treinado — diagnóstico por regra heurística simples (parada &gt; 20 min).';
    }

    // Renderiza Gráfico Chart.js
    const ctx = document
      .getElementById("graficoProducaoCanvas")
      .getContext("2d");
    new Chart(ctx, {
      type: "bar",
      data: {
        labels: dados.grafico_producao.labels,
        datasets: [
          {
            label: "Peças Produzidas",
            data: dados.grafico_producao.valores,
            backgroundColor: "#004380",
            borderRadius: 6,
          },
        ],
      },
      options: {
        responsive: true,
        plugins: { legend: { display: false } },
        scales: { y: { beginAtZero: true } },
      },
    });

    renderizarGraficoTurnos(dados.producao_por_turno);
    renderizarComparativoOps(dados.comparativo_ordens_producao);
  } catch (err) {
    console.error("Erro ao carregar dados do dashboard:", err);
    document.getElementById("iaMensagem").innerText =
      "Não foi possível carregar o dashboard. Tente novamente em instantes.";
  }
}

function renderizarGraficoTurnos(producaoPorTurno) {
  const ctx = document.getElementById("graficoTurnosCanvas").getContext("2d");

  if (!producaoPorTurno || producaoPorTurno.labels.length === 0) {
    ctx.canvas.parentElement.innerHTML +=
      '<p class="text-secondary text-center py-4 mb-0">Nenhum turno encerrado ainda.</p>';
    ctx.canvas.style.display = "none";
    return;
  }

  new Chart(ctx, {
    data: {
      labels: producaoPorTurno.labels,
      datasets: [
        {
          type: "bar",
          label: "Produção (pçs)",
          data: producaoPorTurno.produzido,
          backgroundColor: "#004380",
          borderRadius: 6,
          yAxisID: "yProducao",
        },
        {
          type: "line",
          label: "OEE (%)",
          data: producaoPorTurno.oee,
          borderColor: "#198754",
          backgroundColor: "#198754",
          tension: 0.3,
          yAxisID: "yOee",
        },
      ],
    },
    options: {
      responsive: true,
      interaction: { mode: "index", intersect: false },
      scales: {
        yProducao: {
          type: "linear",
          position: "left",
          beginAtZero: true,
          title: { display: true, text: "Peças" },
        },
        yOee: {
          type: "linear",
          position: "right",
          beginAtZero: true,
          max: 100,
          grid: { drawOnChartArea: false },
          title: { display: true, text: "OEE %" },
        },
      },
    },
  });
}

function renderizarComparativoOps(comparativos) {
  const container = document.getElementById("listaComparativoOps");
  container.innerHTML = "";

  if (!comparativos || comparativos.length === 0) {
    container.innerHTML =
      '<p class="text-secondary text-center py-3 mb-0">Nenhuma Ordem de Produção cadastrada ainda. <a href="ordens_producao.html">Cadastrar</a></p>';
    return;
  }

  comparativos.forEach((op) => {
    const percentual = op.percentual_atingido;
    const corBarra =
      percentual >= 100 ? "bg-success" : percentual >= 60 ? "bg-primary" : "bg-warning";

    const item = document.createElement("div");
    item.className = "mb-3";
    item.innerHTML = `
      <div class="d-flex justify-content-between small">
        <span class="fw-bold">${escaparHtml(op.numero_op)}</span>
        <span class="text-secondary">${percentual}%</span>
      </div>
      <div class="text-secondary small mb-1">${escaparHtml(op.produto_descricao || "Produto não informado")}</div>
      <div class="progress" style="height: 8px;">
        <div class="progress-bar ${corBarra}" style="width: ${Math.min(percentual, 100)}%"></div>
      </div>
      <div class="text-secondary small mt-1">
        ${op.quantidade_produzida.toLocaleString("pt-BR")} / ${op.quantidade_meta.toLocaleString("pt-BR")} pçs
      </div>
    `;
    container.appendChild(item);
  });
}

function escaparHtml(texto) {
  const div = document.createElement("div");
  div.textContent = texto;
  return div.innerHTML;
}
