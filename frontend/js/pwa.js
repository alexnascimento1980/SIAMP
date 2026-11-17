// PWA do SIAMP: registro do service worker, aviso de conexão e botão de
// instalação. Incluído no fim de todas as páginas.
(function () {
  "use strict";

  // --- Service worker ---------------------------------------------------
  if ("serviceWorker" in navigator) {
    window.addEventListener("load", function () {
      navigator.serviceWorker.register("sw.js").catch(function () {
        // Sem HTTPS/localhost ou navegador sem suporte: o app segue
        // funcionando normalmente, só sem o modo offline.
      });
    });
  }

  // --- Aviso de conexão -------------------------------------------------
  var aviso = null;
  var texto = null;

  function garantirAviso() {
    if (aviso) return;
    aviso = document.createElement("div");
    aviso.className =
      "alert alert-warning d-flex align-items-center gap-2 shadow m-0 " +
      "position-fixed bottom-0 start-0 end-0 rounded-0";
    aviso.style.zIndex = "2000";
    aviso.setAttribute("role", "status");
    aviso.hidden = true;

    var icone = document.createElement("i");
    icone.className = "bi bi-wifi-off";
    texto = document.createElement("span");
    texto.className = "flex-grow-1";
    var botao = document.createElement("button");
    botao.type = "button";
    botao.className = "btn btn-sm btn-outline-dark";
    botao.textContent = "Tentar novamente";
    botao.addEventListener("click", function () {
      window.location.reload();
    });

    aviso.appendChild(icone);
    aviso.appendChild(texto);
    aviso.appendChild(botao);
    document.body.appendChild(aviso);
  }

  function mostrarAviso(mensagem) {
    garantirAviso();
    texto.textContent = mensagem;
    aviso.hidden = false;
  }

  function esconderAviso() {
    if (aviso) aviso.hidden = true;
  }

  // Disparado por auth.js quando a API não pôde ser alcançada.
  window.addEventListener("siamp:sem-conexao", function () {
    mostrarAviso("Sem conexão com o servidor. Os dados não puderam ser carregados.");
  });
  window.addEventListener("offline", function () {
    mostrarAviso("Você está sem internet.");
  });
  window.addEventListener("online", function () {
    esconderAviso();
  });
  if (navigator.onLine === false) {
    document.addEventListener("DOMContentLoaded", function () {
      mostrarAviso("Você está sem internet.");
    });
  }

  // --- Botão "Instalar app" (Chrome/Edge no Android e desktop) -----------
  var CHAVE_DISPENSADO = "siamp_instalar_dispensado";
  var pagina = window.location.pathname.split("/").pop() || "login.html";
  var paginasComConvite = ["home.html", "login.html", ""];
  var eventoInstalar = null;

  function foiDispensado() {
    try {
      return window.localStorage.getItem(CHAVE_DISPENSADO) === "1";
    } catch (e) {
      return false;
    }
  }

  function dispensar() {
    try {
      window.localStorage.setItem(CHAVE_DISPENSADO, "1");
    } catch (e) {
      /* sem armazenamento: só não lembra a escolha */
    }
  }

  function mostrarConvite() {
    if (document.getElementById("siampConviteInstalar")) return;
    var caixa = document.createElement("div");
    caixa.id = "siampConviteInstalar";
    caixa.className =
      "alert alert-primary d-flex align-items-center gap-2 shadow m-0 " +
      "position-fixed bottom-0 start-0 end-0 rounded-0";
    caixa.style.zIndex = "1900";

    var msg = document.createElement("span");
    msg.className = "flex-grow-1";
    msg.textContent = "Instale o SIAMP na tela inicial do celular.";

    var instalar = document.createElement("button");
    instalar.type = "button";
    instalar.className = "btn btn-sm btn-primary";
    instalar.textContent = "Instalar";
    instalar.addEventListener("click", function () {
      if (!eventoInstalar) return;
      eventoInstalar.prompt();
      eventoInstalar.userChoice.finally(function () {
        eventoInstalar = null;
        caixa.remove();
      });
    });

    var fechar = document.createElement("button");
    fechar.type = "button";
    fechar.className = "btn-close";
    fechar.setAttribute("aria-label", "Dispensar");
    fechar.addEventListener("click", function () {
      dispensar();
      caixa.remove();
    });

    caixa.appendChild(msg);
    caixa.appendChild(instalar);
    caixa.appendChild(fechar);
    document.body.appendChild(caixa);
  }

  window.addEventListener("beforeinstallprompt", function (evento) {
    evento.preventDefault();
    eventoInstalar = evento;
    if (paginasComConvite.indexOf(pagina) !== -1 && !foiDispensado()) {
      if (document.body) mostrarConvite();
      else document.addEventListener("DOMContentLoaded", mostrarConvite);
    }
  });

  window.addEventListener("appinstalled", function () {
    var caixa = document.getElementById("siampConviteInstalar");
    if (caixa) caixa.remove();
  });
})();
