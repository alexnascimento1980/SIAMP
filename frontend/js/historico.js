const API_BASE_URL =
  window.SIAMP_API_BASE_URL || "http://localhost:8000/api/v1";
let perfilUsuario = null;

document.addEventListener("DOMContentLoaded", () => {
  const token = obterTokenSalvo();
  if (!token) {
    window.location.href = "login.html";
    return;
  }
  perfilUsuario = obterPerfilDoToken(token);
  carregarTurnos();
});

function obterTokenSalvo() {
  return localStorage.getItem("siamp_token");
}

function sair() {
  localStorage.removeItem("siamp_token");
  window.location.href = "login.html";
}

function obterPerfilDoToken(token) {
  try {
    const payloadBase64 = token.split(".")[1];
    const payload = JSON.parse(
      atob(payloadBase64.replace(/-/g, "+").replace(/_/g, "/")),
    );
    return payload.perfil || null;
  } catch (erro) {
    return null;
  }
}

async function chamarApi(caminho, opcoes = {}) {
  const res = await fetch(`${API_BASE_URL}${caminho}`, {
    ...opcoes,
    headers: {
      Authorization: `Bearer ${obterTokenSalvo()}`,
      ...(opcoes.headers || {}),
    },
  });

  if (res.status === 401) {
    localStorage.removeItem("siamp_token");
    window.location.href = "login.html";
    throw new Error("Sessão expirada.");
  }

  return res;
}

async function carregarTurnos() {
  const tbody = document.getElementById("corpoTabelaHistorico");
  tbody.innerHTML = `<tr><td colspan="8" class="text-center text-secondary py-4">Carregando...</td></tr>`;

  try {
    const res = await chamarApi("/turnos/");
    if (!res.ok) throw new Error("Não foi possível carregar o histórico.");
    const turnos = await res.json();
    renderizarTurnos(turnos);
  } catch (erro) {
    console.error(erro);
    tbody.innerHTML = `<tr><td colspan="8" class="text-center text-danger py-4">${erro.message}</td></tr>`;
  }
}

function renderizarTurnos(turnos) {
  const tbody = document.getElementById("corpoTabelaHistorico");
  tbody.innerHTML = "";

  if (turnos.length === 0) {
    tbody.innerHTML = `<tr><td colspan="8" class="text-center text-secondary py-4">Nenhum turno encerrado ainda.</td></tr>`;
    return;
  }

  const podeEditar =
    perfilUsuario === "ADMIN" || perfilUsuario === "SUPERVISOR";

  turnos.forEach((t) => {
    const tr = document.createElement("tr");
    const dataFormatada = new Date(t.data_registro).toLocaleString("pt-BR", {
      day: "2-digit",
      month: "2-digit",
      year: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
    const badgeEficiencia =
      t.eficiencia_oee < 75
        ? `<span class="badge bg-danger">${t.eficiencia_oee}%</span>`
        : `<span class="badge bg-success">${t.eficiencia_oee}%</span>`;
    const badgeQualidade =
      t.indice_qualidade < 95
        ? `<span class="badge bg-warning text-dark">${t.indice_qualidade}%</span>`
        : `<span class="badge bg-success">${t.indice_qualidade}%</span>`;
    const marcaEditado = t.editado
      ? ' <i class="bi bi-pencil-fill text-secondary" title="Turno corrigido"></i>'
      : "";
    const botaoEditar = podeEditar
      ? `<a href="index.html?editar=${t.id}" class="btn btn-sm btn-outline-secondary" title="Corrigir este turno">
           <i class="bi bi-pencil-square"></i>
         </a>`
      : "";

    tr.innerHTML = `
      <td class="fw-bold">${escaparHtml(t.nome_turno)}${marcaEditado}</td>
      <td>${escaparHtml(t.responsavel_nome)}</td>
      <td>${dataFormatada}</td>
      <td class="text-center">${t.total_produzido} pçs</td>
      <td class="text-center">${badgeQualidade}</td>
      <td class="text-center">${badgeEficiencia}</td>
      <td class="text-center"><span class="badge bg-primary">${escaparHtml(t.status_assinatura)}</span></td>
      <td class="text-center">
        <div class="d-flex gap-1 justify-content-center">
          <button class="btn btn-sm btn-outline-primary" onclick="baixarRelatorio(${t.id}, this)">
            <i class="bi bi-file-earmark-pdf me-1"></i>PDF
          </button>
          ${botaoEditar}
        </div>
      </td>
    `;
    tbody.appendChild(tr);
  });
}

// Downloads autenticados não funcionam com <a href> simples (o navegador
// não manda o header Authorization), então buscamos o PDF via fetch e
// disparamos o download a partir do blob retornado.
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
    link.download = `relatorio_turno_${turnoId}.pdf`;
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

function mostrarMensagem(texto, tipo) {
  const el = document.getElementById("alertaMsg");
  el.textContent = texto;
  el.className = `alert alert-${tipo}`;
  el.classList.remove("d-none");
}

function escaparHtml(texto) {
  const div = document.createElement("div");
  div.textContent = texto;
  return div.innerHTML;
}
