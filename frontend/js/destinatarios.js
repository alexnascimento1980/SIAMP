let destinatariosCarregados = [];

document.addEventListener("DOMContentLoaded", async () => {
  const sessao = await exigirSessao();
  if (!sessao) return;

  if (sessao.perfil !== "ADMIN") {
    alert("Apenas administradores podem acessar esta página.");
    window.location.href = "index.html";
    return;
  }

  document
    .getElementById("formNovoDestinatario")
    .addEventListener("submit", onCriarDestinatario);

  carregarDestinatarios();
});

async function carregarDestinatarios() {
  const tbody = document.getElementById("corpoTabelaDestinatarios");
  const incluirInativos = document.getElementById("chkMostrarInativos").checked;

  try {
    const res = await chamarApi(
      `/destinatarios/?incluir_inativos=${incluirInativos}`,
    );
    if (!res.ok) throw new Error("Não foi possível carregar os destinatários.");
    destinatariosCarregados = await res.json();
    renderizarDestinatarios();
  } catch (erro) {
    console.error(erro);
    tbody.innerHTML = `<tr><td colspan="4" class="text-center text-danger py-3">${erro.message}</td></tr>`;
  }
}

function renderizarDestinatarios() {
  const tbody = document.getElementById("corpoTabelaDestinatarios");
  tbody.innerHTML = "";

  if (destinatariosCarregados.length === 0) {
    tbody.innerHTML = `<tr><td colspan="4" class="text-center text-secondary py-3">Nenhum destinatário cadastrado. O sistema usa REPORT_RECIPIENTS do .env enquanto a lista estiver vazia.</td></tr>`;
    return;
  }

  destinatariosCarregados.forEach((d) => {
    const tr = document.createElement("tr");
    const badgeStatus = d.ativo
      ? '<span class="badge bg-success">Ativo</span>'
      : '<span class="badge bg-secondary">Inativo</span>';
    const botaoStatus = d.ativo
      ? `<button class="btn btn-sm btn-outline-danger" onclick="alterarStatus(${d.id}, false)">Desativar</button>`
      : `<button class="btn btn-sm btn-outline-success" onclick="alterarStatus(${d.id}, true)">Reativar</button>`;

    tr.innerHTML = `
      <td class="fw-bold">${escaparHtml(d.email)}</td>
      <td>${escaparHtml(d.nome || "-")}</td>
      <td class="text-center">${badgeStatus}</td>
      <td class="text-center">
        <div class="d-flex gap-1 justify-content-center">
          ${botaoStatus}
          <button class="btn btn-sm btn-outline-danger" title="Remover definitivamente" onclick="removerDestinatario(${d.id})">
            <i class="bi bi-trash"></i>
          </button>
        </div>
      </td>
    `;
    tbody.appendChild(tr);
  });
}

async function onCriarDestinatario(evento) {
  evento.preventDefault();
  esconderMensagem();

  const payload = {
    email: document.getElementById("novoEmail").value.trim(),
    nome: document.getElementById("novoNome").value.trim() || null,
  };

  const btn = document.getElementById("btnCriarDestinatario");
  btn.disabled = true;

  try {
    const res = await chamarApi("/destinatarios/", {
      method: "POST",
      body: JSON.stringify(payload),
    });

    if (res.status === 409) {
      mostrarMensagem("Este e-mail já está cadastrado.", "danger");
      return;
    }

    if (!res.ok) {
      const erro = await res.json().catch(() => null);
      mostrarMensagem(
        erro?.detail || "Não foi possível cadastrar o destinatário.",
        "danger",
      );
      return;
    }

    document.getElementById("formNovoDestinatario").reset();
    mostrarMensagem("Destinatário cadastrado com sucesso!", "success");
    carregarDestinatarios();
  } catch (erro) {
    mostrarMensagem(erro.message, "danger");
  } finally {
    btn.disabled = false;
  }
}

async function alterarStatus(destinatarioId, ativo) {
  try {
    const res = await chamarApi(`/destinatarios/${destinatarioId}`, {
      method: "PATCH",
      body: JSON.stringify({ ativo }),
    });

    if (!res.ok) {
      const erro = await res.json().catch(() => null);
      mostrarMensagem(erro?.detail || "Não foi possível alterar o status.", "danger");
      return;
    }

    carregarDestinatarios();
  } catch (erro) {
    mostrarMensagem(erro.message, "danger");
  }
}

async function removerDestinatario(destinatarioId) {
  if (!confirm("Remover este destinatário definitivamente?")) return;

  try {
    const res = await chamarApi(`/destinatarios/${destinatarioId}`, {
      method: "DELETE",
    });

    if (!res.ok && res.status !== 204) {
      const erro = await res.json().catch(() => null);
      mostrarMensagem(erro?.detail || "Não foi possível remover o destinatário.", "danger");
      return;
    }

    mostrarMensagem("Destinatário removido.", "success");
    carregarDestinatarios();
  } catch (erro) {
    mostrarMensagem(erro.message, "danger");
  }
}

function mostrarMensagem(texto, tipo) {
  const el = document.getElementById("alertaMsg");
  el.textContent = texto;
  el.className = `alert alert-${tipo}`;
  el.classList.remove("d-none");
}

function esconderMensagem() {
  document.getElementById("alertaMsg").classList.add("d-none");
}

function escaparHtml(texto) {
  const div = document.createElement("div");
  div.textContent = texto;
  return div.innerHTML;
}
