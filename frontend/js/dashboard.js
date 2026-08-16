const API_BASE_URL =
  window.SIAMP_API_BASE_URL || "http://localhost:8000/api/v1";

document.addEventListener("DOMContentLoaded", () => {
  if (!obterTokenSalvo()) {
    window.location.href = "login.html";
    return;
  }
  carregarDashboard();
});

function obterTokenSalvo() {
  return localStorage.getItem("siamp_token");
}

function sair() {
  localStorage.removeItem("siamp_token");
  window.location.href = "login.html";
}

async function carregarDashboard() {
  try {
    const res = await fetch(`${API_BASE_URL}/dashboard/metricas-gerais`, {
      headers: { Authorization: `Bearer ${obterTokenSalvo()}` },
    });

    if (res.status === 401) {
      localStorage.removeItem("siamp_token");
      window.location.href = "login.html";
      return;
    }

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
