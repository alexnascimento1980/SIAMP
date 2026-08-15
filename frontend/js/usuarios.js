const API_BASE_URL =
  window.SIAMP_API_BASE_URL || "http://localhost:8000/api/v1";

document.addEventListener("DOMContentLoaded", () => {
  const token = obterTokenSalvo();
  if (!token) {
    window.location.href = "login.html";
    return;
  }

  if (obterPerfilDoToken(token) !== "ADMIN") {
    alert("Apenas administradores podem acessar esta página.");
    window.location.href = "index.html";
    return;
  }

  document
    .getElementById("formNovoUsuario")
    .addEventListener("submit", onCriarUsuario);
  carregarUsuarios();
});

function obterTokenSalvo() {
  return localStorage.getItem("siamp_token");
}

function sair() {
  localStorage.removeItem("siamp_token");
  window.location.href = "login.html";
}

// Leitura client-side do payload do JWT, só para decidir o que mostrar na
// tela (esconder/mostrar menu). O backend SEMPRE revalida a assinatura e a
// permissão de verdade em cada endpoint - isto aqui não é uma camada de
// segurança, é só uma conveniência de UI.
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
      "Content-Type": "application/json",
      Authorization: `Bearer ${obterTokenSalvo()}`,
      ...(opcoes.headers || {}),
    },
  });

  if (res.status === 401) {
    localStorage.removeItem("siamp_token");
    window.location.href = "login.html";
    throw new Error("Sessão expirada.");
  }

  if (res.status === 403) {
    throw new Error("Você não tem permissão para esta ação.");
  }

  return res;
}

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
