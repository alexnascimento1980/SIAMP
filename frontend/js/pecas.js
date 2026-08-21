let pecasCarregadas = [];
let modalEditar = null;

document.addEventListener("DOMContentLoaded", async () => {
  const sessao = await exigirSessao();
  if (!sessao) return;

  if (sessao.perfil !== "ADMIN" && sessao.perfil !== "SUPERVISOR") {
    alert("Apenas administradores e supervisores podem acessar esta página.");
    window.location.href = "home.html";
    return;
  }

  modalEditar = new bootstrap.Modal(document.getElementById("modalEditarPeca"));

  document
    .getElementById("formNovaPeca")
    .addEventListener("submit", onCriarPeca);
  document
    .getElementById("formEditarPeca")
    .addEventListener("submit", onSalvarEdicao);

  carregarPecas();
});

async function carregarPecas() {
  const tbody = document.getElementById("corpoTabelaPecas");
  const incluirInativas = document.getElementById("chkMostrarInativas").checked;

  try {
    const res = await chamarApi(
      `/produtos/?incluir_inativas=${incluirInativas}`,
    );
    if (!res.ok) throw new Error("Não foi possível carregar as peças.");
    pecasCarregadas = await res.json();
    renderizarPecas();
  } catch (erro) {
    console.error(erro);
    tbody.innerHTML = `<tr><td colspan="7" class="text-center text-danger py-3">${erro.message}</td></tr>`;
  }
}

function renderizarPecas() {
  const tbody = document.getElementById("corpoTabelaPecas");
  tbody.innerHTML = "";

  const filtro = document
    .getElementById("filtroPecas")
    .value.trim()
    .toLowerCase();

  const pecas = filtro
    ? pecasCarregadas.filter(
        (p) =>
          p.codigo.toLowerCase().includes(filtro) ||
          p.descricao.toLowerCase().includes(filtro),
      )
    : pecasCarregadas;

  if (pecas.length === 0) {
    tbody.innerHTML = `<tr><td colspan="7" class="text-center text-secondary py-3">Nenhuma peça encontrada.</td></tr>`;
    return;
  }

  pecas.forEach((p) => {
    const tr = document.createElement("tr");
    const badgeStatus = p.ativo
      ? '<span class="badge bg-success">Ativa</span>'
      : '<span class="badge bg-secondary">Inativa</span>';
    const botaoStatus = p.ativo
      ? `<button class="btn btn-sm btn-outline-danger" onclick="alterarStatus(${p.id}, false)">Desativar</button>`
      : `<button class="btn btn-sm btn-outline-success" onclick="alterarStatus(${p.id}, true)">Reativar</button>`;

    tr.innerHTML = `
      <td class="fw-bold">${escaparHtml(p.codigo)}</td>
      <td>${escaparHtml(p.descricao)}</td>
      <td class="text-center">${p.ciclo_padrao ?? "-"}</td>
      <td class="text-center">${p.cavidades ?? "-"}</td>
      <td class="text-center">${p.peso_gramas ?? "-"}</td>
      <td class="text-center">${badgeStatus}</td>
      <td class="text-center">
        <div class="d-flex gap-1 justify-content-center">
          <button class="btn btn-sm btn-outline-secondary" onclick="abrirEdicao(${p.id})" title="Editar">
            <i class="bi bi-pencil-square"></i>
          </button>
          ${botaoStatus}
        </div>
      </td>
    `;
    tbody.appendChild(tr);
  });
}

async function onCriarPeca(evento) {
  evento.preventDefault();
  esconderMensagem();

  const payload = {
    codigo: document.getElementById("novoCodigo").value.trim(),
    descricao: document.getElementById("novaDescricao").value.trim(),
    ciclo_padrao: valorOpcionalNumerico("novoCiclo"),
    cavidades: valorOpcionalNumerico("novaCavidades"),
    peso_gramas: valorOpcionalNumerico("novoPeso"),
  };

  const btn = document.getElementById("btnCriarPeca");
  btn.disabled = true;

  try {
    const res = await chamarApi("/produtos/", {
      method: "POST",
      body: JSON.stringify(payload),
    });

    if (res.status === 409) {
      mostrarMensagem("Já existe uma peça cadastrada com este código.", "danger");
      return;
    }

    if (!res.ok) {
      const erro = await res.json().catch(() => null);
      mostrarMensagem(
        erro?.detail || "Não foi possível cadastrar a peça.",
        "danger",
      );
      return;
    }

    document.getElementById("formNovaPeca").reset();
    mostrarMensagem("Peça cadastrada com sucesso!", "success");
    carregarPecas();
  } catch (erro) {
    mostrarMensagem(erro.message, "danger");
  } finally {
    btn.disabled = false;
  }
}

function abrirEdicao(pecaId) {
  const peca = pecasCarregadas.find((p) => p.id === pecaId);
  if (!peca) return;

  document.getElementById("editId").value = peca.id;
  document.getElementById("editCodigo").value = peca.codigo;
  document.getElementById("editDescricao").value = peca.descricao;
  document.getElementById("editCiclo").value = peca.ciclo_padrao ?? "";
  document.getElementById("editCavidades").value = peca.cavidades ?? "";
  document.getElementById("editPeso").value = peca.peso_gramas ?? "";

  modalEditar.show();
}

async function onSalvarEdicao(evento) {
  evento.preventDefault();

  const pecaId = document.getElementById("editId").value;
  const payload = {
    codigo: document.getElementById("editCodigo").value.trim(),
    descricao: document.getElementById("editDescricao").value.trim(),
    ciclo_padrao: valorOpcionalNumerico("editCiclo"),
    cavidades: valorOpcionalNumerico("editCavidades"),
    peso_gramas: valorOpcionalNumerico("editPeso"),
  };

  try {
    const res = await chamarApi(`/produtos/${pecaId}`, {
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
    mostrarMensagem("Peça atualizada com sucesso!", "success");
    carregarPecas();
  } catch (erro) {
    mostrarMensagem(erro.message, "danger");
  }
}

async function alterarStatus(pecaId, ativo) {
  try {
    const res = await chamarApi(`/produtos/${pecaId}`, {
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

    carregarPecas();
  } catch (erro) {
    mostrarMensagem(erro.message, "danger");
  }
}

function valorOpcionalNumerico(idCampo) {
  const valor = document.getElementById(idCampo).value;
  return valor === "" ? null : parseFloat(valor);
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
