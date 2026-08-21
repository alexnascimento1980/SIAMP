let maquinasCarregadas = [];
let modalEditar = null;

document.addEventListener("DOMContentLoaded", async () => {
  const sessao = await exigirSessao();
  if (!sessao) return;

  if (sessao.perfil !== "ADMIN" && sessao.perfil !== "SUPERVISOR") {
    alert("Apenas administradores e supervisores podem acessar esta página.");
    window.location.href = "home.html";
    return;
  }

  modalEditar = new bootstrap.Modal(document.getElementById("modalEditarMaquina"));

  document
    .getElementById("formNovaMaquina")
    .addEventListener("submit", onCriarMaquina);
  document
    .getElementById("formEditarMaquina")
    .addEventListener("submit", onSalvarEdicao);

  carregarMaquinas();
});

async function carregarMaquinas() {
  const tbody = document.getElementById("corpoTabelaMaquinas");
  const incluirInativas = document.getElementById("chkMostrarInativas").checked;

  try {
    const res = await chamarApi(
      `/maquinas/?incluir_inativas=${incluirInativas}`,
    );
    if (!res.ok) throw new Error("Não foi possível carregar as máquinas.");
    maquinasCarregadas = await res.json();
    renderizarMaquinas(maquinasCarregadas);
  } catch (erro) {
    console.error(erro);
    tbody.innerHTML = `<tr><td colspan="4" class="text-center text-danger py-3">${erro.message}</td></tr>`;
  }
}

function renderizarMaquinas(maquinas) {
  const tbody = document.getElementById("corpoTabelaMaquinas");
  tbody.innerHTML = "";

  if (maquinas.length === 0) {
    tbody.innerHTML = `<tr><td colspan="4" class="text-center text-secondary py-3">Nenhuma injetora cadastrada.</td></tr>`;
    return;
  }

  maquinas.forEach((m) => {
    const tr = document.createElement("tr");
    const badgeStatus = m.ativo
      ? '<span class="badge bg-success">Ativa</span>'
      : '<span class="badge bg-secondary">Inativa</span>';
    const botaoStatus = m.ativo
      ? `<button class="btn btn-sm btn-outline-danger" onclick="alterarStatus(${m.id}, false)">Desativar</button>`
      : `<button class="btn btn-sm btn-outline-success" onclick="alterarStatus(${m.id}, true)">Reativar</button>`;

    tr.innerHTML = `
      <td class="fw-bold">${escaparHtml(m.numero_maquina)}</td>
      <td>${escaparHtml(m.descricao || "-")}</td>
      <td class="text-center">${badgeStatus}</td>
      <td class="text-center">
        <div class="d-flex gap-1 justify-content-center">
          <button class="btn btn-sm btn-outline-secondary" onclick="abrirEdicao(${m.id})" title="Editar">
            <i class="bi bi-pencil-square"></i>
          </button>
          ${botaoStatus}
          <button class="btn btn-sm btn-outline-danger" title="Excluir definitivamente" onclick="excluirMaquina(${m.id})">
            <i class="bi bi-trash"></i>
          </button>
        </div>
      </td>
    `;
    tbody.appendChild(tr);
  });
}

async function onCriarMaquina(evento) {
  evento.preventDefault();
  esconderMensagem();

  const payload = {
    numero_maquina: document.getElementById("novoNumero").value.trim(),
    descricao: document.getElementById("novaDescricao").value.trim() || null,
  };

  const btn = document.getElementById("btnCriarMaquina");
  btn.disabled = true;

  try {
    const res = await chamarApi("/maquinas/", {
      method: "POST",
      body: JSON.stringify(payload),
    });

    if (res.status === 409) {
      mostrarMensagem(
        "Já existe uma injetora cadastrada com este número.",
        "danger",
      );
      return;
    }

    if (!res.ok) {
      const erro = await res.json().catch(() => null);
      mostrarMensagem(
        erro?.detail || "Não foi possível cadastrar a injetora.",
        "danger",
      );
      return;
    }

    document.getElementById("formNovaMaquina").reset();
    mostrarMensagem("Injetora cadastrada com sucesso!", "success");
    carregarMaquinas();
  } catch (erro) {
    mostrarMensagem(erro.message, "danger");
  } finally {
    btn.disabled = false;
  }
}

function abrirEdicao(maquinaId) {
  const maquina = maquinasCarregadas.find((m) => m.id === maquinaId);
  if (!maquina) return;

  document.getElementById("editId").value = maquina.id;
  document.getElementById("editNumero").value = maquina.numero_maquina;
  document.getElementById("editDescricao").value = maquina.descricao || "";

  modalEditar.show();
}

async function onSalvarEdicao(evento) {
  evento.preventDefault();

  const maquinaId = document.getElementById("editId").value;
  const payload = {
    descricao: document.getElementById("editDescricao").value.trim() || null,
  };

  try {
    const res = await chamarApi(`/maquinas/${maquinaId}`, {
      method: "PATCH",
      body: JSON.stringify(payload),
    });

    if (!res.ok) {
      const erro = await res.json().catch(() => null);
      mostrarMensagem(
        erro?.detail || "Não foi possível salvar as alterações.",
        "danger",
      );
      return;
    }

    modalEditar.hide();
    mostrarMensagem("Injetora atualizada com sucesso!", "success");
    carregarMaquinas();
  } catch (erro) {
    mostrarMensagem(erro.message, "danger");
  }
}

async function alterarStatus(maquinaId, ativo) {
  try {
    const res = await chamarApi(`/maquinas/${maquinaId}`, {
      method: "PATCH",
      body: JSON.stringify({ ativo }),
    });

    if (!res.ok) {
      const erro = await res.json().catch(() => null);
      mostrarMensagem(
        erro?.detail || "Não foi possível alterar o status.",
        "danger",
      );
      return;
    }

    carregarMaquinas();
  } catch (erro) {
    mostrarMensagem(erro.message, "danger");
  }
}

async function excluirMaquina(maquinaId) {
  if (!confirm("Excluir esta injetora definitivamente? Isso só é possível se ela nunca teve produção registrada.")) {
    return;
  }

  try {
    const res = await chamarApi(`/maquinas/${maquinaId}`, { method: "DELETE" });

    if (res.status === 409) {
      const erro = await res.json().catch(() => null);
      mostrarMensagem(
        erro?.detail || "Não é possível excluir: esta máquina já tem histórico vinculado.",
        "warning",
      );
      return;
    }

    if (!res.ok && res.status !== 204) {
      const erro = await res.json().catch(() => null);
      mostrarMensagem(erro?.detail || "Não foi possível excluir.", "danger");
      return;
    }

    mostrarMensagem("Injetora excluída.", "success");
    carregarMaquinas();
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
