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

/**
 * Extrai uma mensagem de erro legível do corpo de uma resposta de
 * erro da API. `erro.detail` normalmente é uma string simples (a
 * maioria dos erros do backend, ex.: HTTPException com detail="..."),
 * mas numa resposta 422 de validação do Pydantic é uma LISTA de
 * objetos (ex.: [{"type": "value_error", "loc": [...], "msg": "...",
 * ...}]) - sem tratar esse segundo formato, o valor acaba renderizado
 * na tela como "[object Object]" (toString padrão de um array de
 * objetos em JavaScript), inútil para quem está usando o sistema.
 * Use isto em vez de `erro?.detail || "mensagem padrão"` diretamente.
 */
function extrairMensagemDeErro(erro, mensagemPadrao) {
  const detalhe = erro?.detail;
  if (!detalhe) return mensagemPadrao;
  if (typeof detalhe === "string") return detalhe;
  if (Array.isArray(detalhe)) {
    const mensagens = detalhe
      .map((item) => (typeof item === "string" ? item : item?.msg))
      .filter(Boolean);
    return mensagens.length > 0 ? mensagens.join(" ") : mensagemPadrao;
  }
  return mensagemPadrao;
}
