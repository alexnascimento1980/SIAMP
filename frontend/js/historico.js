let perfilUsuario = null;
let turnosSelecionados = new Set();

document.addEventListener("DOMContentLoaded", async () => {
  const sessao = await exigirSessao();
  if (!sessao) return;
  perfilUsuario = sessao.perfil;
  carregarTurnos();
});

async function carregarTurnos() {
  turnosSelecionados.clear();
  atualizarBarraAcaoLote();
  const tbody = document.getElementById("corpoTabelaHistorico");
  tbody.innerHTML = `<tr><td colspan="9" class="text-center text-secondary py-4">Carregando...</td></tr>`;

  try {
    const res = await chamarApi("/turnos/");
    if (!res.ok) throw new Error("Não foi possível carregar o histórico.");
    const turnos = await res.json();
    renderizarTurnos(turnos);
  } catch (erro) {
    console.error(erro);
    tbody.innerHTML = `<tr><td colspan="9" class="text-center text-danger py-4">${erro.message}</td></tr>`;
  }
}

function renderizarTurnos(turnos) {
  const tbody = document.getElementById("corpoTabelaHistorico");
  tbody.innerHTML = "";

  if (turnos.length === 0) {
    tbody.innerHTML = `<tr><td colspan="9" class="text-center text-secondary py-4">Nenhum turno encerrado ainda.</td></tr>`;
    return;
  }

  const podeEditar =
    perfilUsuario === "ADMIN" || perfilUsuario === "SUPERVISOR";

  // Coluna de seleção só existe para quem pode marcar/desmarcar turnos
  // como teste (mesma permissão de corrigir turno) - operador não vê
  // checkbox nenhum.
  document.getElementById("colunaSelecaoTodos").classList.toggle("d-none", !podeEditar);

  turnos.forEach((t) => {
    const tr = document.createElement("tr");
    const dataFormatada = new Date(t.data_registro).toLocaleString("pt-BR", {
      day: "2-digit",
      month: "2-digit",
      year: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
    const emAndamento = t.status_assinatura === "EM_ANDAMENTO";
    const badgeEficiencia =
      t.eficiencia_oee < 75
        ? `<span class="badge bg-danger">${t.eficiencia_oee}%</span>`
        : `<span class="badge bg-success">${t.eficiencia_oee}%</span>`;
    const badgeQualidade =
      t.indice_qualidade < 95
        ? `<span class="badge bg-warning text-dark">${t.indice_qualidade}%</span>`
        : `<span class="badge bg-success">${t.indice_qualidade}%</span>`;
    const badgeStatus = emAndamento
      ? `<span class="badge bg-warning text-dark">Em andamento</span>`
      : `<span class="badge bg-success">Fechado</span>`;
    const marcaEditado = t.editado
      ? ' <i class="bi bi-pencil-fill text-secondary" title="Turno corrigido"></i>'
      : "";
    const badgeTeste = t.marcado_teste
      ? ' <span class="badge bg-secondary" title="Excluído do dashboard e dos relatórios">TESTE</span>'
      : "";
    const checkboxSelecao = podeEditar
      ? `<td class="text-center">
           <input type="checkbox" class="form-check-input check-turno" value="${t.id}"
             ${turnosSelecionados.has(t.id) ? "checked" : ""}
             onchange="alternarSelecaoTurno(${t.id}, this.checked)">
         </td>`
      : "";

    // Turno em andamento: continuar preenchendo (liberado para
    // qualquer usuário - é o rascunho da própria pessoa). Turno já
    // fechado: corrigir é restrito a ADMIN/SUPERVISOR.
    // Turno em andamento: continuar preenchendo (liberado para
    // qualquer usuário - é o rascunho da própria pessoa). Turno já
    // fechado: corrigir é restrito a ADMIN/SUPERVISOR. A página certa
    // (nova, por lançamento, ou antiga, por hora) depende do modelo
    // com que o turno foi criado - turnos antigos continuam usando a
    // grade por hora para sempre.
    const paginaApontamento =
      t.modelo_apontamento === "LANCAMENTO" ? "apontamento.html" : "apontamento_horario.html";
    const botaoEditar = emAndamento
      ? `<a href="${paginaApontamento}?rascunho=${t.id}" class="btn btn-sm btn-outline-warning" title="Continuar preenchendo este turno">
           <i class="bi bi-pencil-square"></i>
         </a>`
      : podeEditar
        ? `<a href="${paginaApontamento}?editar=${t.id}" class="btn btn-sm btn-outline-secondary" title="Corrigir este turno">
             <i class="bi bi-pencil-square"></i>
           </a>`
        : "";
    // Reenvio de e-mail só faz sentido para turno já fechado (é o
    // único caso em que um e-mail original já foi enviado).
    const botaoReenviarEmail = !emAndamento && podeEditar
      ? `<button class="btn btn-sm btn-outline-secondary" title="Reenviar relatório por e-mail" onclick="reenviarEmail(${t.id}, this)">
           <i class="bi bi-envelope-arrow-up"></i>
         </button>`
      : "";

    tr.innerHTML = `
      ${checkboxSelecao}
      <td class="fw-bold">${escaparHtml(t.nome_turno)}${marcaEditado}${badgeTeste}</td>
      <td>${escaparHtml(t.responsavel_nome)}</td>
      <td>${dataFormatada}</td>
      <td class="text-center">${t.total_produzido} pçs</td>
      <td class="text-center">${badgeQualidade}</td>
      <td class="text-center">${badgeEficiencia}</td>
      <td class="text-center">${badgeStatus}</td>
      <td class="text-center">
        <div class="d-flex gap-1 justify-content-center">
          <button class="btn btn-sm btn-outline-primary" onclick="baixarRelatorio(${t.id}, this)">
            <i class="bi bi-file-earmark-pdf me-1"></i>PDF
          </button>
          ${botaoReenviarEmail}
          ${botaoEditar}
        </div>
      </td>
    `;
    tbody.appendChild(tr);
  });
}

// Com autenticação via cookie, um <a href> simples já enviaria o cookie
// de sessão automaticamente. Mesmo assim buscamos o PDF via fetch (com
// chamarApi, que trata sessão expirada) e disparamos o download a partir
// do blob retornado, para manter o spinner de carregamento no botão e o
// tratamento de erro consistente com o resto da tela.
async function baixarRelatorio(turnoId, botao) {
  const textoOriginal = botao.innerHTML;
  botao.disabled = true;
  botao.innerHTML = `<span class="spinner-border spinner-border-sm"></span>`;

  try {
    const res = await chamarApi(`/turnos/${turnoId}/relatorio.pdf`);
    if (!res.ok) throw new Error("Não foi possível gerar o relatório.");

    const blob = await res.blob();
    const url = window.URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    // O nome do arquivo (com turno + data) vem do backend via
    // Content-Disposition, em vez de remontado aqui - assim os dois
    // lugares (download manual e anexo do e-mail) nunca ficam
    // divergentes.
    link.download =
      extrairNomeArquivo(res) || `relatorio_turno_${turnoId}.pdf`;
    document.body.appendChild(link);
    link.click();
    link.remove();
    window.URL.revokeObjectURL(url);
  } catch (erro) {
    mostrarMensagem(erro.message, "danger");
  } finally {
    botao.disabled = false;
    botao.innerHTML = textoOriginal;
  }
}

function extrairNomeArquivo(res) {
  const cabecalho = res.headers.get("Content-Disposition");
  if (!cabecalho) return null;
  const match = cabecalho.match(/filename="?([^"]+)"?/);
  return match ? match[1] : null;
}

async function exportarCsv() {
  const btn = document.getElementById("btnExportarCsv");
  const textoOriginal = btn.innerHTML;
  btn.disabled = true;
  btn.innerHTML = `<span class="spinner-border spinner-border-sm"></span>`;

  const dataInicio = document.getElementById("exportDataInicio").value;
  const dataFim = document.getElementById("exportDataFim").value;
  const params = new URLSearchParams();
  if (dataInicio) params.set("data_inicio", dataInicio);
  if (dataFim) params.set("data_fim", dataFim);
  const query = params.toString() ? `?${params.toString()}` : "";

  try {
    const res = await chamarApi(`/turnos/exportar/csv${query}`);
    if (!res.ok) throw new Error("Não foi possível gerar a exportação.");

    const blob = await res.blob();
    const url = window.URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = extrairNomeArquivo(res) || "apontamentos_siamp.csv";
    document.body.appendChild(link);
    link.click();
    link.remove();
    window.URL.revokeObjectURL(url);
  } catch (erro) {
    mostrarMensagem(erro.message, "danger");
  } finally {
    btn.disabled = false;
    btn.innerHTML = textoOriginal;
  }
}

async function reenviarEmail(turnoId, botao) {
  if (!confirm("Reenviar o relatório deste turno por e-mail para os destinatários configurados?")) {
    return;
  }

  const textoOriginal = botao.innerHTML;
  botao.disabled = true;
  botao.innerHTML = `<span class="spinner-border spinner-border-sm"></span>`;

  try {
    const res = await chamarApi(`/turnos/${turnoId}/reenviar-email`, {
      method: "POST",
    });

    if (res.status === 409) {
      mostrarMensagem(
        "Envio de e-mail não está configurado neste ambiente (faltam SMTP_USER/SMTP_PASS/REPORT_RECIPIENTS no .env).",
        "warning",
      );
      return;
    }

    if (!res.ok) {
      const erro = await res.json().catch(() => null);
      throw new Error(erro?.detail || "Não foi possível reenviar o relatório.");
    }

    mostrarMensagem("Relatório reenviado por e-mail com sucesso!", "success");
  } catch (erro) {
    mostrarMensagem(erro.message, "danger");
  } finally {
    botao.disabled = false;
    botao.innerHTML = textoOriginal;
  }
}

function mostrarMensagem(texto, tipo) {
  const el = document.getElementById("alertaMsg");
  el.textContent = texto;
  el.className = `alert alert-${tipo}`;
  el.classList.remove("d-none");
}

function alternarSelecaoTurno(turnoId, marcado) {
  if (marcado) {
    turnosSelecionados.add(turnoId);
  } else {
    turnosSelecionados.delete(turnoId);
    // desmarca também o "selecionar todos", já que nem tudo está mais selecionado
    document.getElementById("checkSelecionarTodos").checked = false;
  }
  atualizarBarraAcaoLote();
}

function alternarSelecionarTodos(marcarTodos) {
  document.querySelectorAll(".check-turno").forEach((checkbox) => {
    checkbox.checked = marcarTodos;
    const turnoId = parseInt(checkbox.value);
    if (marcarTodos) {
      turnosSelecionados.add(turnoId);
    } else {
      turnosSelecionados.delete(turnoId);
    }
  });
  atualizarBarraAcaoLote();
}

function limparSelecao() {
  turnosSelecionados.clear();
  document.querySelectorAll(".check-turno").forEach((c) => (c.checked = false));
  const checkTodos = document.getElementById("checkSelecionarTodos");
  if (checkTodos) checkTodos.checked = false;
  atualizarBarraAcaoLote();
}

function atualizarBarraAcaoLote() {
  const barra = document.getElementById("barraAcaoLote");
  const contador = document.getElementById("contadorSelecionados");
  const quantidade = turnosSelecionados.size;

  barra.classList.toggle("d-none", quantidade === 0);
  contador.innerText = `${quantidade} selecionado${quantidade === 1 ? "" : "s"}`;
}

async function marcarSelecionadosComoTeste(marcadoTeste) {
  if (turnosSelecionados.size === 0) return;

  const acao = marcadoTeste ? "marcar" : "desmarcar";
  if (!confirm(`${marcadoTeste ? "Marcar" : "Desmarcar"} ${turnosSelecionados.size} turno(s) como teste? Turnos marcados saem do dashboard e dos relatórios, mas continuam aqui no Histórico.`)) {
    return;
  }

  try {
    const res = await chamarApi("/turnos/marcar-teste", {
      method: "PATCH",
      body: JSON.stringify({
        turno_ids: Array.from(turnosSelecionados),
        marcado_teste: marcadoTeste,
      }),
    });

    if (!res.ok) {
      const erro = await res.json().catch(() => null);
      throw new Error(erro?.detail || `Não foi possível ${acao} os turnos selecionados.`);
    }

    mostrarMensagem(
      `${turnosSelecionados.size} turno(s) ${marcadoTeste ? "marcado(s)" : "desmarcado(s)"} como teste.`,
      "success",
    );
    limparSelecao();
    carregarTurnos();
  } catch (erro) {
    mostrarMensagem(erro.message, "danger");
  }
}

function escaparHtml(texto) {
  const div = document.createElement("div");
  div.textContent = texto;
  return div.innerHTML;
}
