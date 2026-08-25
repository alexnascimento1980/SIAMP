// Autenticação compartilhada por todas as telas.
//
// A sessão agora é mantida pelo backend via cookie httpOnly (definido em
// /auth/login), então o JavaScript do frontend não guarda mais o JWT em
// localStorage nem o decodifica no cliente — isso reduz o impacto de um
// eventual XSS, já que um script malicioso injetado na página não
// consegue ler ou exfiltrar o token de um cookie httpOnly.
//
// Este arquivo deve ser incluído (via <script>) ANTES do script
// específico de cada página (apontamento.js, dashboard.js, historico.js,
// maquinas.js, usuarios.js).

const API_BASE_URL =
  window.SIAMP_API_BASE_URL || "http://localhost:8000/api/v1";

/**
 * Wrapper de fetch que sempre envia o cookie de sessão (`credentials:
 * "include"`) e trata sessão expirada/ausente de forma centralizada.
 * Use isto em vez de fetch() puro para chamar a API autenticada.
 */
async function chamarApi(caminho, opcoes = {}) {
  const ehFormData = opcoes.body instanceof FormData;
  const precisaJson =
    opcoes.body !== undefined && !ehFormData && !(opcoes.headers || {})["Content-Type"];

  const res = await fetch(`${API_BASE_URL}${caminho}`, {
    ...opcoes,
    credentials: "include",
    headers: {
      ...(precisaJson ? { "Content-Type": "application/json" } : {}),
      ...(opcoes.headers || {}),
    },
  });

  if (res.status === 401) {
    window.location.href = "login.html";
    throw new Error("Sessão expirada.");
  }

  return res;
}

/**
 * Confere se existe uma sessão válida (via GET /auth/me, que só responde
 * 200 se o cookie httpOnly for válido) e retorna os dados do usuário
 * logado ({ id, nome, email, perfil }). Redireciona para o login e
 * retorna null se não houver sessão.
 */
async function exigirSessao() {
  try {
    const res = await fetch(`${API_BASE_URL}/auth/me`, {
      credentials: "include",
    });
    if (!res.ok) throw new Error("sem sessão");
    return await res.json();
  } catch (erro) {
    window.location.href = "login.html";
    return null;
  }
}

/** Encerra a sessão (limpa o cookie no backend) e volta para o login. */
async function sair() {
  try {
    await fetch(`${API_BASE_URL}/auth/logout`, {
      method: "POST",
      credentials: "include",
    });
  } finally {
    window.location.href = "login.html";
  }
}
