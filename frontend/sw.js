// Service worker do SIAMP (PWA).
//
// O que faz:
//   - Guarda a "casca" do app (HTML, CSS, JS, ícones, Bootstrap, Chart.js)
//     para o app abrir mesmo sem sinal.
//   - Páginas e scripts do próprio SIAMP: rede primeiro (com limite de
//     tempo); se a rede falhar ou demorar, usa a cópia guardada. Assim um
//     deploy novo chega na hora para quem está online.
//   - Bibliotecas de terceiros (vendor/) e imagens: cache primeiro.
//
// O que NÃO faz, de propósito:
//   - NUNCA intercepta /api/. Dados de produção, sessão e relatórios vêm
//     sempre da rede. Nada de dado de usuário fica em cache no aparelho
//     (importante em celular compartilhado entre operadores).
//
// Para forçar a renovação do cache de todos os aparelhos, aumente VERSAO.

const VERSAO = "v1";
const CACHE = `siamp-${VERSAO}`;
const LIMITE_REDE_MS = 4000;

const CASCA = [
  "offline.html",
  "manifest.webmanifest",
  "login.html",
  "home.html",
  "apontamento.html",
  "apontamento_horario.html",
  "dashboard.html",
  "destinatarios.html",
  "historico.html",
  "maquinas.html",
  "ordens_producao.html",
  "pecas.html",
  "usuarios.html",
  "css/styles.css",
  "js/acoes.js",
  "js/config.js",
  "js/auth.js",
  "js/pwa.js",
  "js/login.js",
  "js/home.js",
  "js/apontamento.js",
  "js/apontamento_horario.js",
  "js/dashboard.js",
  "js/destinatarios.js",
  "js/historico.js",
  "js/maquinas.js",
  "js/ordens_producao.js",
  "js/pecas.js",
  "js/usuarios.js",
  "img/siamp-logo.png",
  "img/siamp-logo-branco.png",
  "img/pwa/icon-192.png",
  "img/pwa/icon-512.png",
  "favicon-16.png",
  "favicon-32.png",
  "apple-touch-icon.png",
  "vendor/bootstrap/css/bootstrap.min.css",
  "vendor/bootstrap/js/bootstrap.bundle.min.js",
  "vendor/bootstrap-icons/bootstrap-icons.min.css",
  "vendor/bootstrap-icons/fonts/bootstrap-icons.woff2",
  "vendor/bootstrap-icons/fonts/bootstrap-icons.woff",
  "vendor/chartjs/chart.umd.min.js",
];

self.addEventListener("install", (evento) => {
  evento.waitUntil(
    caches
      .open(CACHE)
      // cache: "reload" ignora o cache HTTP do navegador: guarda a versão
      // realmente atual do servidor.
      .then((cache) =>
        cache.addAll(CASCA.map((url) => new Request(url, { cache: "reload" })))
      )
      .then(() => self.skipWaiting())
  );
});

self.addEventListener("activate", (evento) => {
  evento.waitUntil(
    caches
      .keys()
      .then((nomes) =>
        Promise.all(
          nomes
            .filter((n) => n.startsWith("siamp-") && n !== CACHE)
            .map((n) => caches.delete(n))
        )
      )
      .then(() => self.clients.claim())
  );
});

function comLimite(promessa, ms) {
  return new Promise((resolver, rejeitar) => {
    const t = setTimeout(() => rejeitar(new Error("tempo esgotado")), ms);
    promessa.then(
      (r) => {
        clearTimeout(t);
        resolver(r);
      },
      (e) => {
        clearTimeout(t);
        rejeitar(e);
      }
    );
  });
}

async function guardar(requisicao, resposta) {
  // Só guarda respostas completas e bem-sucedidas do próprio site.
  if (resposta && resposta.ok && resposta.type === "basic" && !resposta.redirected) {
    const cache = await caches.open(CACHE);
    await cache.put(requisicao, resposta.clone());
  }
  return resposta;
}

async function daCopia(requisicao) {
  const cache = await caches.open(CACHE);
  return (
    (await cache.match(requisicao)) ||
    (await cache.match(requisicao, { ignoreSearch: true }))
  );
}

async function redePrimeiro(requisicao) {
  try {
    // cache: "no-cache" = revalida com o servidor (304 se não mudou), sem
    // cair numa cópia velha do cache HTTP do navegador.
    const resposta = await comLimite(
      fetch(requisicao, { cache: "no-cache" }),
      LIMITE_REDE_MS
    );
    // 5xx do nginx (backend acordando etc.) não deve apagar uma cópia boa.
    if (resposta.status >= 500) {
      const copia = await daCopia(requisicao);
      return copia || resposta;
    }
    return await guardar(requisicao, resposta);
  } catch (erro) {
    const copia = await daCopia(requisicao);
    if (copia) return copia;
    if (requisicao.mode === "navigate") {
      const url = new URL(requisicao.url);
      const cache = await caches.open(CACHE);
      if (url.pathname === "/") {
        const login = await cache.match("login.html");
        if (login) return login;
      }
      const offline = await cache.match("offline.html");
      if (offline) return offline;
    }
    throw erro;
  }
}

async function cachePrimeiro(requisicao) {
  const copia = await daCopia(requisicao);
  if (copia) return copia;
  const resposta = await fetch(requisicao);
  return guardar(requisicao, resposta);
}

self.addEventListener("fetch", (evento) => {
  const req = evento.request;
  if (req.method !== "GET") return;

  const url = new URL(req.url);
  if (url.origin !== self.location.origin) return;
  if (url.pathname.startsWith("/api/")) return; // sempre direto na rede
  if (url.pathname === "/sw.js") return;

  if (url.pathname.startsWith("/vendor/") || url.pathname.startsWith("/img/")) {
    evento.respondWith(cachePrimeiro(req));
    return;
  }

  evento.respondWith(redePrimeiro(req));
});
