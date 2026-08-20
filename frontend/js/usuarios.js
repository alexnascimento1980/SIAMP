document.addEventListener("DOMContentLoaded", async () => {
  const sessao = await exigirSessao();
  if (!sessao) return;

  if (sessao.perfil !== "ADMIN") {
    alert("Apenas administradores podem acessar esta página.");
    window.location.href = "home.html";
    return;
  }

  document
    .getElementById("formNovoUsuario")
    .addEventListener("submit", onCriarUsuario);
  carregarUsuarios();
});

async function carregarUsuarios() {
  const tbody = document.getElementById("corpoTabelaUsuarios");
  try {
    const res = await chamarApi("/usuarios/");
    if (!res.ok) throw new Error("Não foi possível carregar os usuários.");
    const usuarios = await res.json();
    renderizarUsuarios(usuarios);
  } catch (erro) {
    console.error(erro);
    tbody.innerHTML = `<tr><td colspan="5" class="text-center text-danger py-3">${erro.message}</td></tr>`;
  }
}

function renderizarUsuarios(usuarios) {
  const tbody = document.getElementById("corpoTabelaUsuarios");
  tbody.innerHTML = "";

  if (usuarios.length === 0) {
    tbody.innerHTML = `<tr><td colspan="5" class="text-center text-secondary py-3">Nenhum usuário cadastrado.</td></tr>`;
    return;
  }

  usuarios.forEach((u) => {
    const tr = document.createElement("tr");
    const badgeStatus = u.ativo
      ? '<span class="badge bg-success">Ativo</span>'
      : '<span class="badge bg-secondary">Inativo</span>';
    const botaoAcao = u.ativo
      ? `<button class="btn btn-sm btn-outline-danger" onclick="alterarStatus(${u.id}, false)">Desativar</button>`
      : `<button class="btn btn-sm btn-outline-success" onclick="alterarStatus(${u.id}, true)">Reativar</button>`;

    tr.innerHTML = `
      <td>${escaparHtml(u.nome)}</td>
      <td>${escaparHtml(u.email)}</td>
      <td><span class="badge bg-primary">${escaparHtml(u.perfil)}</span></td>
      <td class="text-center">${badgeStatus}</td>
      <td class="text-center">${botaoAcao}</td>
    `;
    tbody.appendChild(tr);
  });
}

async function onCriarUsuario(evento) {
  evento.preventDefault();
  esconderMensagem();

  const payload = {
    nome: document.getElementById("novoNome").value.trim(),
    email: document.getElementById("novoEmail").value.trim(),
    senha: document.getElementById("novaSenha").value,
    perfil: document.getElementById("novoPerfil").value,
  };

  const btn = document.getElementById("btnCriar");
  btn.disabled = true;

  try {
    const res = await chamarApi("/usuarios/", {
      method: "POST",
      body: JSON.stringify(payload),
    });

    if (res.status === 409) {
      mostrarMensagem(
        "Já existe um usuário cadastrado com este e-mail.",
        "danger",
      );
      return;
    }

    if (!res.ok) {
      const erro = await res.json().catch(() => null);
      mostrarMensagem(
        erro?.detail || "Não foi possível cadastrar o usuário.",
        "danger",
      );
      return;
    }

    document.getElementById("formNovoUsuario").reset();
    mostrarMensagem("Usuário cadastrado com sucesso!", "success");
    carregarUsuarios();
  } catch (erro) {
    mostrarMensagem(erro.message, "danger");
  } finally {
    btn.disabled = false;
  }
}

async function alterarStatus(usuarioId, ativo) {
  try {
    const res = await chamarApi(`/usuarios/${usuarioId}/status`, {
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

    carregarUsuarios();
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
