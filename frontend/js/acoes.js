// Delegação de eventos declarativa - substitui os handlers inline
// (onclick="...", onchange="...", oninput="...") das telas.
//
// Por quê: handlers inline obrigam o CSP a liberar 'unsafe-inline' em
// script-src, o que anula a principal defesa do navegador contra XSS
// (qualquer HTML injetado com onerror=/onclick= passaria a executar).
// Sem eles, o nginx pode servir script-src sem 'unsafe-inline'.
//
// Como usar, no HTML (estático ou gerado em template literal):
//
//   <button data-onclick="removerLancamento" data-args='[3]'>
//   <select data-onchange="salvarValor" data-args='["05:00","prod","@@value"]'>
//
// e, no JS da página, registrar as funções chamáveis (lista fechada -
// um nome que não foi registrado nunca é executado, mesmo que o atributo
// exista no HTML):
//
//   registrarAcoes({ removerLancamento, salvarValor });
//
// Argumentos especiais (resolvidos no momento do evento, no elemento que
// carrega o atributo data-on...):
//   "@@el"        o próprio elemento (antigo `this`)
//   "@@value"     el.value            (antigo `this.value`)
//   "@@checked"   el.checked          (antigo `this.checked`)
//   "@@data.xxx"  el.dataset.xxx      (antigo `this.dataset.xxx`)
//
// Este arquivo deve ser incluído ANTES de auth.js e dos scripts de página.

(function () {
  const acoes = Object.create(null);

  window.registrarAcoes = function registrarAcoes(mapa) {
    Object.keys(mapa).forEach((nome) => {
      if (typeof mapa[nome] === "function") {
        acoes[nome] = mapa[nome];
      }
    });
  };

  function resolverArgumento(arg, el) {
    if (typeof arg !== "string" || !arg.startsWith("@@")) return arg;
    const chave = arg.slice(2);
    if (chave === "el") return el;
    if (chave === "value") return el.value;
    if (chave === "checked") return el.checked;
    if (chave.startsWith("data.")) return el.dataset[chave.slice(5)];
    return arg;
  }

  function tratar(evento) {
    const alvo = evento.target;
    if (!alvo || typeof alvo.closest !== "function") return;

    const atributo = "data-on" + evento.type;
    const el = alvo.closest("[" + atributo + "]");
    if (!el) return;

    const nome = el.getAttribute(atributo);
    const funcao = acoes[nome];
    if (!funcao) {
      console.error("Ação não registrada: " + nome);
      return;
    }

    let args = [];
    const bruto = el.getAttribute("data-args");
    if (bruto) {
      try {
        args = JSON.parse(bruto);
      } catch (erro) {
        console.error("data-args inválido em " + nome + ":", erro);
        return;
      }
      if (!Array.isArray(args)) args = [args];
    }

    funcao(...args.map((a) => resolverArgumento(a, el)));
  }

  ["click", "change", "input"].forEach((tipo) => {
    document.addEventListener(tipo, tratar);
  });
})();
