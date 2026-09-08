document.addEventListener("DOMContentLoaded", async () => {
  const sessao = await exigirSessao();
  if (!sessao) return;

  document.querySelectorAll('input[name="periodo"]').forEach((radio) => {
    radio.addEventListener("change", () => {
      const ehPersonalizado = radio.value === "personalizado";
      document.getElementById("filtroPersonalizado").classList.toggle("d-none", !ehPersonalizado);
      // "Personalizado" só recarrega quando o usuário escolher as
      // datas e clicar em Aplicar - os outros períodos continuam
      // recarregando assim que selecionados, sem mudança nenhuma.
      if (!ehPersonalizado) {
        carregarDashboard(radio.value);
      }
    });
  });

  document.getElementById("btnAplicarPersonalizado").addEventListener("click", aplicarPeriodoPersonalizado);

  carregarDashboard("total");
});

function aplicarPeriodoPersonalizado() {
  const erroEl = document.getElementById("erroPersonalizado");
  erroEl.classList.add("d-none");

  const dataInicio = document.getElementById("dataInicioPersonalizado").value;
  const dataFim = document.getElementById("dataFimPersonalizado").value;

  if (!dataInicio || !dataFim) {
    erroEl.innerText = "Preencha as duas datas.";
    erroEl.classList.remove("d-none");
    return;
  }
  if (dataFim < dataInicio) {
    erroEl.innerText = "A data final não pode ser anterior à data inicial.";
    erroEl.classList.remove("d-none");
    return;
  }

  carregarDashboard("personalizado", dataInicio, dataFim);
}

const ROTULOS_PERIODO = {
  diario: "- hoje",
  semanal: "- últimos 7 dias",
  mensal: "- últimos 30 dias",
  total: "",
};

function rotuloPeriodo(dados) {
  if (dados.periodo === "personalizado" && dados.data_inicio && dados.data_fim) {
    const formatar = (iso) => iso.split("-").reverse().join("/");
    return `- de ${formatar(dados.data_inicio)} até ${formatar(dados.data_fim)}`;
  }
  return ROTULOS_PERIODO[dados.periodo] || "";
}

// Guarda as instâncias já criadas do Chart.js - trocar de período
// dispara uma nova busca e recria os gráficos, e o Chart.js exige
// destruir a instância anterior antes de reusar o mesmo <canvas>,
// senão lança erro ("Canvas is already in use").
let graficoProducaoInstancia = null;
let graficoTurnosInstancia = null;

async function carregarDashboard(periodo = "total", dataInicio = null, dataFim = null) {
  try {
    let caminho = `/dashboard/metricas-gerais?periodo=${periodo}`;
    if (periodo === "personalizado" && dataInicio && dataFim) {
      caminho += `&data_inicio=${dataInicio}&data_fim=${dataFim}`;
    }
    const res = await chamarApi(caminho);

    if (!res.ok) {
      if (periodo === "personalizado") {
        const erro = await res.json().catch(() => null);
        const erroEl = document.getElementById("erroPersonalizado");
        erroEl.innerText = extrairMensagemDeErro(erro, "Não foi possível aplicar o período.");
        erroEl.classList.remove("d-none");
        return;
      }
      throw new Error(`Falha ao carregar dashboard (HTTP ${res.status})`);
    }

    const dados = await res.json();

    document.getElementById("rotuloPeriodoGrafico").innerText = rotuloPeriodo(dados);

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

    // Deixa claro a origem do diagnóstico - modelo scikit-learn
    // treinado, heurística de fallback (enquanto o modelo não existe
    // ou não pôde ser carregado), ou nenhum lançamento de produção
    // ainda registrado para basear qualquer diagnóstico.
    const fonteEl = document.getElementById("iaFonteTexto");
    if (dados.insight_ml.fonte === "modelo_ml") {
      fonteEl.innerHTML =
        '<i class="bi bi-cpu me-1"></i>Modelo de Machine Learning treinado, prevendo o risco de parada não programada na próxima produção desta injetora.';
    } else if (dados.insight_ml.fonte === "heuristica") {
      fonteEl.innerHTML =
        '<i class="bi bi-exclamation-triangle me-1"></i>Modelo ainda não treinado — diagnóstico por regra heurística (histórico de falha + divergência de ciclo).';
    } else {
      fonteEl.innerHTML =
        '<i class="bi bi-info-circle me-1"></i>Ainda não há lançamentos de produção suficientes para gerar um diagnóstico.';
    }

    // Sinais que embasaram o diagnóstico - dá transparência ao "porquê"
    // em vez de só mostrar um percentual sem explicação.
    const detalheContainer = document.getElementById("iaDetalheContainer");
    const listaDetalhe = document.getElementById("iaListaDetalhe");
    const detalhe = dados.insight_ml.detalhe;
    if (detalhe && Object.keys(detalhe).length > 0) {
      listaDetalhe.innerHTML = `
        <li>Divergência do ciclo real vs. padrão da peça: <strong>${detalhe.ciclo_divergencia_pct}%</strong></li>
        <li>Histórico de falha desta injetora: <strong>${detalhe.taxa_falha_historica_maquina}%</strong></li>
        <li>Histórico de falha desta peça: <strong>${detalhe.taxa_falha_historica_peca}%</strong></li>
      `;
      detalheContainer.classList.remove("d-none");
    } else {
      detalheContainer.classList.add("d-none");
    }

    // Renderiza Gráfico Chart.js
    const ctx = document
      .getElementById("graficoProducaoCanvas")
      .getContext("2d");
    if (graficoProducaoInstancia) graficoProducaoInstancia.destroy();
    graficoProducaoInstancia = new Chart(ctx, {
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
  if (graficoTurnosInstancia) {
    graficoTurnosInstancia.destroy();
    graficoTurnosInstancia = null;
  }

  if (!producaoPorTurno || producaoPorTurno.labels.length === 0) {
    const mensagemExistente = ctx.canvas.parentElement.querySelector(".mensagem-sem-turnos");
    if (!mensagemExistente) {
      ctx.canvas.insertAdjacentHTML(
        "afterend",
        '<p class="mensagem-sem-turnos text-secondary text-center py-4 mb-0">Nenhum turno encerrado ainda.</p>',
      );
    }
    ctx.canvas.style.display = "none";
    return;
  }
  ctx.canvas.style.display = "";
  const mensagemAntiga = ctx.canvas.parentElement.querySelector(".mensagem-sem-turnos");
  if (mensagemAntiga) mensagemAntiga.remove();

  graficoTurnosInstancia = new Chart(ctx, {
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
