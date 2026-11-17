// Fila offline do SIAMP: guarda no aparelho (IndexedDB) os turnos que o
// operador finalizou sem sinal e os envia sozinha quando a conexão volta.
//
// Garantias:
//   - Sem duplicar: cada fechamento carrega um id_envio (UUID); se o envio
//     se repetir (resposta perdida, duas abas, reenvio), o servidor devolve
//     o turno que já existe.
//   - Sem trocar de autor: cada item guarda o usuário que finalizou o turno
//     e só é enviado quando ESSE usuário está logado (celular compartilhado).
//   - Sem perder dado: erro de rede/servidor mantém o item na fila; recusa
//     do servidor (dado inválido) mantém o item visível, com o motivo, para
//     o operador baixar os dados ou descartar - nunca some sozinho.
//
// Também guarda cópia dos cadastros (máquinas, peças, OPs) para a tela de
// apontamento abrir sem sinal. Incluído depois de auth.js nas telas logadas.
(function () {
  "use strict";

  const NOME_BD = "siamp-offline";
  const VERSAO_BD = 1;
  const INTERVALO_REENVIO_MS = 60000;

  let bdPromessa = null;
  let enviando = false;
  let usuarioAtual = null; // { id, nome } da sessão atual (cache em memória)

  function abrirBd() {
    if (bdPromessa) return bdPromessa;
    bdPromessa = new Promise(function (resolver, rejeitar) {
      if (!("indexedDB" in window)) return rejeitar(new Error("sem IndexedDB"));
      const req = window.indexedDB.open(NOME_BD, VERSAO_BD);
      req.onupgradeneeded = function () {
        const bd = req.result;
        if (!bd.objectStoreNames.contains("fila")) {
          bd.createObjectStore("fila", { keyPath: "id_envio" });
        }
        if (!bd.objectStoreNames.contains("catalogos")) {
          bd.createObjectStore("catalogos", { keyPath: "chave" });
        }
      };
      req.onsuccess = function () {
        resolver(req.result);
      };
      req.onerror = function () {
        rejeitar(req.error);
      };
    });
    // Se falhar (ex.: navegação privada), a próxima chamada tenta de novo.
    bdPromessa.catch(function () {
      bdPromessa = null;
    });
    return bdPromessa;
  }

  function operar(loja, modo, fn) {
    return abrirBd().then(function (bd) {
      return new Promise(function (resolver, rejeitar) {
        const tx = bd.transaction(loja, modo);
        const armazem = tx.objectStore(loja);
        let resultado;
        const pedido = fn(armazem);
        if (pedido) {
          pedido.onsuccess = function () {
            resultado = pedido.result;
          };
        }
        tx.oncomplete = function () {
          resolver(resultado);
        };
        tx.onerror = function () {
          rejeitar(tx.error);
        };
        tx.onabort = function () {
          rejeitar(tx.error || new Error("transação cancelada"));
        };
      });
    });
  }

  // --- Fila --------------------------------------------------------------

  function listar() {
    return operar("fila", "readonly", function (s) {
      return s.getAll();
    }).then(function (itens) {
      return (itens || []).sort(function (a, b) {
        return a.criado_em < b.criado_em ? -1 : 1;
      });
    });
  }

  function gravarItem(item) {
    return operar("fila", "readwrite", function (s) {
      return s.put(item);
    });
  }

  function remover(idEnvio) {
    return operar("fila", "readwrite", function (s) {
      return s.delete(idEnvio);
    });
  }

  /**
   * Guarda um fechamento para envio posterior. `item` precisa de:
   * id_envio, caminho, metodo, payload, usuario_id, usuario_nome.
   * Rejeita se o aparelho não conseguiu gravar - quem chama NÃO deve dizer
   * ao operador que o turno foi guardado nesse caso.
   */
  function enfileirar(item) {
    const registro = {
      id_envio: item.id_envio,
      caminho: item.caminho,
      metodo: item.metodo,
      payload: item.payload,
      usuario_id: item.usuario_id,
      usuario_nome: item.usuario_nome || "",
      criado_em: new Date().toISOString(),
      status: "pendente",
      tentativas: 0,
      ultimo_erro: "",
    };
    return gravarItem(registro).then(function () {
      renderizar();
      return registro;
    });
  }

  function contarPendentesDoUsuario(usuarioId) {
    return listar().then(function (itens) {
      return itens.filter(function (i) {
        return i.usuario_id === usuarioId;
      }).length;
    });
  }

  // --- Cópia dos cadastros -------------------------------------------------

  function salvarCatalogo(chave, dados) {
    return operar("catalogos", "readwrite", function (s) {
      return s.put({ chave: chave, dados: dados, salvo_em: new Date().toISOString() });
    }).catch(function () {
      /* sem armazenamento: só perde a cópia offline */
    });
  }

  function lerCatalogo(chave) {
    return operar("catalogos", "readonly", function (s) {
      return s.get(chave);
    }).catch(function () {
      return undefined;
    });
  }

  // --- Envio -----------------------------------------------------------------

  async function descobrirUsuario() {
    if (usuarioAtual) return usuarioAtual;
    try {
      const res = await fetch(API_BASE_URL + "/auth/me", { credentials: "include" });
      if (!res.ok) return null;
      const u = await res.json();
      usuarioAtual = { id: u.id, nome: u.nome };
      return usuarioAtual;
    } catch (e) {
      return null;
    }
  }

  async function enviarUm(item) {
    let res;
    try {
      res = await fetch(API_BASE_URL + item.caminho, {
        method: item.metodo,
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(item.payload),
      });
    } catch (e) {
      return { resultado: "adiar", motivo: "sem conexão" };
    }
    if (res.ok) return { resultado: "enviado" };
    if (res.status === 401) return { resultado: "login" };
    if (res.status >= 500 || res.status === 408 || res.status === 429) {
      return { resultado: "adiar", motivo: "servidor indisponível (" + res.status + ")" };
    }
    let corpo = null;
    try {
      corpo = await res.json();
    } catch (e) {
      /* corpo sem JSON */
    }
    return {
      resultado: "recusado",
      motivo: extrairMensagemDeErro(corpo, "Recusado pelo servidor (" + res.status + ").") ,
    };
  }

  async function processarFila() {
    const resumo = { enviados: 0, restantes: 0, precisaLogin: false };
    const usuario = await descobrirUsuario();
    if (!usuario) {
      resumo.precisaLogin = true;
      return resumo;
    }
    const itens = await listar();
    for (const item of itens) {
      if (item.status !== "pendente") continue;
      if (item.usuario_id !== usuario.id) continue;
      const r = await enviarUm(item);
      if (r.resultado === "enviado") {
        await remover(item.id_envio);
        resumo.enviados += 1;
      } else if (r.resultado === "recusado") {
        item.status = "recusado";
        item.ultimo_erro = r.motivo;
        await gravarItem(item);
      } else if (r.resultado === "login") {
        usuarioAtual = null;
        resumo.precisaLogin = true;
        break;
      } else {
        item.tentativas += 1;
        item.ultimo_erro = r.motivo;
        await gravarItem(item);
        break; // mantém a ordem: tenta de novo mais tarde
      }
    }
    resumo.restantes = (await listar()).length;
    return resumo;
  }

  async function enviarPendentes() {
    if (enviando) return null;
    enviando = true;
    try {
      const executar = function () {
        return processarFila();
      };
      let resumo;
      if (navigator.locks && navigator.locks.request) {
        // Uma aba por vez (o id_envio já protege de duplicar, isto só evita trabalho repetido).
        resumo = await navigator.locks.request("siamp-fila", { ifAvailable: true }, function (lock) {
          return lock ? executar() : null;
        });
      } else {
        resumo = await executar();
      }
      if (resumo && resumo.enviados > 0) {
        mostrarMensagem(
          resumo.enviados === 1 ? "1 turno enviado com sucesso." : resumo.enviados + " turnos enviados com sucesso."
        );
        window.dispatchEvent(new CustomEvent("siamp:fila-enviada", { detail: resumo }));
      }
      return resumo;
    } catch (e) {
      return null;
    } finally {
      enviando = false;
      renderizar();
    }
  }

  // --- Painel de pendentes -----------------------------------------------------

  let painel = null;
  let expandido = false;
  let mensagemTemporaria = "";
  let temporizadorMensagem = null;

  function mostrarMensagem(texto) {
    mensagemTemporaria = texto;
    clearTimeout(temporizadorMensagem);
    temporizadorMensagem = setTimeout(function () {
      mensagemTemporaria = "";
      renderizar();
    }, 8000);
  }

  function formatarData(iso) {
    try {
      return new Date(iso).toLocaleString("pt-BR", {
        day: "2-digit",
        month: "2-digit",
        hour: "2-digit",
        minute: "2-digit",
      });
    } catch (e) {
      return iso;
    }
  }

  function baixarJson(item) {
    const blob = new Blob([JSON.stringify(item, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "turno-nao-enviado-" + item.id_envio.slice(0, 8) + ".json";
    document.body.appendChild(a);
    a.click();
    a.remove();
    setTimeout(function () {
      URL.revokeObjectURL(url);
    }, 1000);
  }

  function criarEl(tag, classe, texto) {
    const el = document.createElement(tag);
    if (classe) el.className = classe;
    if (texto !== undefined) el.textContent = texto;
    return el;
  }

  function botao(texto, classe, aoClicar) {
    const b = criarEl("button", "btn btn-sm " + classe, texto);
    b.type = "button";
    b.addEventListener("click", aoClicar);
    return b;
  }

  async function renderizar() {
    let itens = [];
    try {
      itens = await listar();
    } catch (e) {
      itens = [];
    }

    if (itens.length === 0 && !mensagemTemporaria) {
      if (painel) {
        painel.remove();
        painel = null;
      }
      return;
    }

    const barra = document.querySelector("nav.navbar");
    if (!barra) return;
    if (!painel) {
      painel = criarEl("div", "alert alert-info m-2 mb-0");
      painel.setAttribute("role", "status");
      barra.insertAdjacentElement("afterend", painel);
    }
    painel.replaceChildren();

    const meu = usuarioAtual ? usuarioAtual.id : null;
    const pendentes = itens.filter(function (i) {
      return i.status === "pendente";
    });
    const recusados = itens.filter(function (i) {
      return i.status === "recusado";
    });

    if (mensagemTemporaria) {
      painel.className = "alert alert-success m-2 mb-0";
      painel.appendChild(criarEl("div", "", "✅ " + mensagemTemporaria));
    } else {
      painel.className = recusados.length ? "alert alert-danger m-2 mb-0" : "alert alert-info m-2 mb-0";
    }

    if (itens.length > 0) {
      const linha = criarEl("div", "d-flex flex-wrap align-items-center gap-2");
      const partes = [];
      if (pendentes.length) {
        partes.push(
          pendentes.length + (pendentes.length === 1 ? " turno aguardando envio" : " turnos aguardando envio")
        );
      }
      if (recusados.length) {
        partes.push(
          recusados.length + (recusados.length === 1 ? " turno recusado pelo servidor" : " turnos recusados pelo servidor")
        );
      }
      linha.appendChild(criarEl("span", "flex-grow-1 fw-semibold", "📤 " + partes.join(" · ")));
      if (pendentes.length) {
        linha.appendChild(
          botao("Enviar agora", "btn-primary", function () {
            enviarPendentes();
          })
        );
      }
      linha.appendChild(
        botao(expandido ? "Ocultar" : "Ver", "btn-outline-secondary", function () {
          expandido = !expandido;
          renderizar();
        })
      );
      painel.appendChild(linha);
    }

    if (expandido) {
      const lista = criarEl("ul", "list-group mt-2");
      itens.forEach(function (item) {
        const li = criarEl("li", "list-group-item");
        const qtd = (item.payload.lancamentos || []).length;
        li.appendChild(
          criarEl(
            "div",
            "fw-semibold",
            (item.payload.nome_turno || "Turno") + " · líder " + (item.payload.responsavel_nome || "?")
          )
        );
        li.appendChild(
          criarEl(
            "div",
            "small text-muted",
            "Finalizado em " +
              formatarData(item.payload.fechado_em || item.criado_em) +
              " · " +
              qtd +
              (qtd === 1 ? " lançamento" : " lançamentos") +
              " · por " +
              (item.usuario_nome || "usuário " + item.usuario_id)
          )
        );
        if (item.status === "recusado") {
          li.appendChild(criarEl("div", "small text-danger mt-1", "Recusado: " + item.ultimo_erro));
          const acoes = criarEl("div", "d-flex gap-2 mt-2");
          acoes.appendChild(
            botao("Baixar dados", "btn-outline-secondary", function () {
              baixarJson(item);
            })
          );
          acoes.appendChild(
            botao("Descartar", "btn-outline-danger", async function () {
              if (!window.confirm("Descartar este turno? Os dados serão apagados deste aparelho.")) return;
              await remover(item.id_envio);
              renderizar();
            })
          );
          li.appendChild(acoes);
        } else {
          if (meu !== null && item.usuario_id !== meu) {
            li.appendChild(
              criarEl(
                "div",
                "small text-warning-emphasis mt-1",
                "Será enviado quando " + (item.usuario_nome || "o usuário que o criou") + " entrar neste aparelho."
              )
            );
          } else if (item.ultimo_erro) {
            li.appendChild(criarEl("div", "small text-muted mt-1", "Última tentativa: " + item.ultimo_erro));
          }
        }
        lista.appendChild(li);
      });
      painel.appendChild(lista);
    }
  }

  // --- Disparo automático ------------------------------------------------------

  const naTelaDeLogin = /login\.html$/.test(window.location.pathname);

  function iniciar() {
    if (naTelaDeLogin) return;
    descobrirUsuario().then(function () {
      renderizar();
      if (navigator.onLine !== false) enviarPendentes();
    });
    window.addEventListener("online", function () {
      enviarPendentes();
    });
    window.addEventListener("siamp:fila-enviar", function () {
      enviarPendentes();
    });
    setInterval(function () {
      if (document.visibilityState === "visible" && navigator.onLine !== false) enviarPendentes();
    }, INTERVALO_REENVIO_MS);
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", iniciar);
  else iniciar();

  window.FilaOffline = {
    enfileirar: enfileirar,
    listar: listar,
    contarPendentesDoUsuario: contarPendentesDoUsuario,
    enviarPendentes: enviarPendentes,
    salvarCatalogo: salvarCatalogo,
    lerCatalogo: lerCatalogo,
    atualizarPainel: renderizar,
  };
})();
