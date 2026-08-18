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
            backgroundColor: "#0d6efd",
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
  } catch (err) {
    console.error("Erro ao carregar dados do dashboard:", err);
    document.getElementById("iaMensagem").innerText =
      "Não foi possível carregar o dashboard. Tente novamente em instantes.";
  }
}
