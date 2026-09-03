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
    const nomeEscapado = escaparHtml(u.nome).replace(/'/g, "\\'");

    // Conta protegida: Desativar/Excluir ficam desabilitados, com
    // dica explicando o motivo - evita repetir o mesmo acidente que
    // motivou essa proteção (um ADMIN excluindo a conta de outro),
    // em vez de só bloquear no backend depois do clique.
    const botaoAcao = u.protegido
      ? `<button class="btn btn-sm btn-outline-secondary" disabled title="Conta protegida - remova a proteção para desativar">Desativar</button>`
      : u.ativo
      ? `<button class="btn btn-sm btn-outline-danger" onclick="alterarStatus(${u.id}, false)">Desativar</button>`
      : `<button class="btn btn-sm btn-outline-success" onclick="alterarStatus(${u.id}, true)">Reativar</button>`;
    const botaoReset = `<button class="btn btn-sm btn-outline-secondary" onclick="abrirResetSenha(${u.id}, '${nomeEscapado}')" title="Resetar senha">
      <i class="bi bi-key"></i>
    </button>`;
    const botaoExcluir = u.protegido
      ? `<button class="btn btn-sm btn-outline-secondary" disabled title="Conta protegida - remova a proteção para excluir">
          <i class="bi bi-trash"></i>
        </button>`
      : `<button class="btn btn-sm btn-outline-danger" onclick="abrirExcluirUsuario(${u.id}, '${nomeEscapado}')" title="Excluir definitivamente">
          <i class="bi bi-trash"></i>
        </button>`;
    const botaoProtegido = `<button class="btn btn-sm ${u.protegido ? "btn-warning" : "btn-outline-secondary"}" onclick="alternarProtecao(${u.id}, ${!u.protegido}, '${nomeEscapado}')" title="${u.protegido ? "Remover proteção contra exclusão/desativação" : "Proteger contra exclusão/desativação acidental"}">
      <i class="bi bi-shield-lock${u.protegido ? "-fill" : ""}"></i>
    </button>`;
    const perfilClicavel = `<span class="badge bg-primary" role="button" onclick="abrirAlterarPerfil(${u.id}, '${nomeEscapado}', '${u.perfil}')" title="Clique para alterar">
      ${escaparHtml(u.perfil)} <i class="bi bi-pencil-square ms-1" style="font-size: 0.7em;"></i>
    </span>`;
    const marcaProtegido = u.protegido
      ? ' <i class="bi bi-shield-lock-fill text-warning" title="Conta protegida contra exclusão/desativação"></i>'
      : "";

    tr.innerHTML = `
      <td>${escaparHtml(u.nome)}${marcaProtegido}</td>
      <td>${escaparHtml(u.email)}</td>
      <td>${perfilClicavel}</td>
      <td class="text-center">${badgeStatus}</td>
      <td class="text-center"><div class="d-flex gap-1 justify-content-center">${botaoProtegido}${botaoReset}${botaoAcao}${botaoExcluir}</div></td>
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
        extrairMensagemDeErro(erro, "Não foi possível cadastrar o usuário."),
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
        extrairMensagemDeErro(erro, "Não foi possível alterar o status."),
        "danger",
      );
      return;
    }

    carregarUsuarios();
  } catch (erro) {
    mostrarMensagem(erro.message, "danger");
  }
}

async function alternarProtecao(usuarioId, protegido, nomeUsuario) {
  // Sem modal de confirmação de propósito - ação reversível e de
  // baixo risco (diferente de excluir/desativar), não precisa da
  // mesma fricção. Confirma só ao DESPROTEGER, já que essa ação
  // remove justamente a rede de segurança contra o próximo acidente.
  if (!protegido && !confirm(`Remover a proteção de "${nomeUsuario}"? A conta ficará vulnerável a exclusão/desativação novamente.`)) {
    return;
  }

  try {
    const res = await chamarApi(`/usuarios/${usuarioId}/protegido`, {
      method: "PATCH",
      body: JSON.stringify({ protegido }),
    });

    if (!res.ok) {
      const erro = await res.json().catch(() => null);
      mostrarMensagem(
        extrairMensagemDeErro(erro, "Não foi possível alterar a proteção."),
        "danger",
      );
      return;
    }

    mostrarMensagem(
      protegido
        ? `"${nomeUsuario}" agora está protegida contra exclusão/desativação acidental.`
        : `Proteção removida de "${nomeUsuario}".`,
      "success",
    );
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

let usuarioIdParaResetar = null;
let modalResetSenha = null;

function abrirResetSenha(usuarioId, nomeUsuario) {
  usuarioIdParaResetar = usuarioId;
  document.getElementById("resetNomeUsuario").innerText = nomeUsuario;
  document.getElementById("resetNovaSenha").value = "";
  document.getElementById("resetConfirmarSenha").value = "";
  document.getElementById("resetErro").classList.add("d-none");

  if (!modalResetSenha) {
    modalResetSenha = new bootstrap.Modal(document.getElementById("modalResetSenha"));
  }
  modalResetSenha.show();
}

async function confirmarResetSenha() {
  const novaSenha = document.getElementById("resetNovaSenha").value;
  const confirmarSenha = document.getElementById("resetConfirmarSenha").value;
  const erroEl = document.getElementById("resetErro");
  erroEl.classList.add("d-none");

  if (novaSenha.length < 8) {
    erroEl.innerText = "A senha precisa ter pelo menos 8 caracteres.";
    erroEl.classList.remove("d-none");
    return;
  }
  if (novaSenha !== confirmarSenha) {
    erroEl.innerText = "As senhas digitadas não coincidem.";
    erroEl.classList.remove("d-none");
    return;
  }

  const btn = document.getElementById("btnConfirmarReset");
  btn.disabled = true;

  try {
    const res = await chamarApi(`/usuarios/${usuarioIdParaResetar}/senha`, {
      method: "PATCH",
      body: JSON.stringify({ nova_senha: novaSenha }),
    });

    if (!res.ok) {
      const erro = await res.json().catch(() => null);
      erroEl.innerText = extrairMensagemDeErro(erro, "Não foi possível resetar a senha.");
      erroEl.classList.remove("d-none");
      return;
    }

    modalResetSenha.hide();
    mostrarMensagem("Senha redefinida com sucesso.", "success");
  } catch (erro) {
    erroEl.innerText = erro.message;
    erroEl.classList.remove("d-none");
  } finally {
    btn.disabled = false;
  }
}

let usuarioIdParaAlterarPerfil = null;
let modalAlterarPerfil = null;

function abrirAlterarPerfil(usuarioId, nomeUsuario, perfilAtual) {
  usuarioIdParaAlterarPerfil = usuarioId;
  document.getElementById("perfilNomeUsuario").innerText = nomeUsuario;
  document.getElementById("perfilNovoValor").value = perfilAtual;
  document.getElementById("perfilErro").classList.add("d-none");

  if (!modalAlterarPerfil) {
    modalAlterarPerfil = new bootstrap.Modal(document.getElementById("modalAlterarPerfil"));
  }
  modalAlterarPerfil.show();
}

async function confirmarAlterarPerfil() {
  const novoPerfil = document.getElementById("perfilNovoValor").value;
  const erroEl = document.getElementById("perfilErro");
  erroEl.classList.add("d-none");

  const btn = document.getElementById("btnConfirmarPerfil");
  btn.disabled = true;

  try {
    const res = await chamarApi(`/usuarios/${usuarioIdParaAlterarPerfil}/perfil`, {
      method: "PATCH",
      body: JSON.stringify({ perfil: novoPerfil }),
    });

    if (!res.ok) {
      const erro = await res.json().catch(() => null);
      erroEl.innerText = extrairMensagemDeErro(erro, "Não foi possível alterar o perfil.");
      erroEl.classList.remove("d-none");
      return;
    }

    modalAlterarPerfil.hide();
    mostrarMensagem("Perfil alterado com sucesso.", "success");
    carregarUsuarios();
  } catch (erro) {
    erroEl.innerText = erro.message;
    erroEl.classList.remove("d-none");
  } finally {
    btn.disabled = false;
  }
}

let usuarioIdParaExcluir = null;
let modalExcluirUsuario = null;

function abrirExcluirUsuario(usuarioId, nomeUsuario) {
  usuarioIdParaExcluir = usuarioId;
  document.getElementById("excluirNomeUsuario").innerText = nomeUsuario;
  document.getElementById("excluirErro").classList.add("d-none");

  if (!modalExcluirUsuario) {
    modalExcluirUsuario = new bootstrap.Modal(document.getElementById("modalExcluirUsuario"));
  }
  modalExcluirUsuario.show();
}

async function confirmarExcluirUsuario() {
  const erroEl = document.getElementById("excluirErro");
  erroEl.classList.add("d-none");

  const btn = document.getElementById("btnConfirmarExclusao");
  btn.disabled = true;

  try {
    const res = await chamarApi(`/usuarios/${usuarioIdParaExcluir}`, {
      method: "DELETE",
    });

    if (!res.ok) {
      const erro = await res.json().catch(() => null);
      erroEl.innerText = extrairMensagemDeErro(erro, "Não foi possível excluir o usuário.");
      erroEl.classList.remove("d-none");
      return;
    }

    modalExcluirUsuario.hide();
    mostrarMensagem("Usuário excluído definitivamente.", "success");
    carregarUsuarios();
  } catch (erro) {
    erroEl.innerText = erro.message;
    erroEl.classList.remove("d-none");
  } finally {
    btn.disabled = false;
  }
}
