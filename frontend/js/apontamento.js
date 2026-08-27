// Estado: lancamentosState[numero_maquina] = [ {tipo, horario_inicio, horario_fim, produto_id, ordem_producao_id, quantidade, motivo}, ... ]
let lancamentosState = {};
let maquinasDisponiveis = [];
let pecasDisponiveis = [];
let ordensProducaoDisponiveis = [];
let maquinaAtiva = null;
let indiceEditando = null; // índice do lançamento sendo corrigido (dentro de lancamentosState[maquinaAtiva]), ou null se estiver adicionando um novo

let turnoEditandoId = null; // corrigir turno LANCAMENTO já fechado (ADMIN/SUPERVISOR)
let rascunhoTurnoId = null; // continuar um rascunho LANCAMENTO em andamento

document.addEventListener("DOMContentLoaded", async () => {
  const sessao = await exigirSessao();
  if (!sessao) return;

  const perfil = sessao.perfil;
  if (perfil === "ADMIN") {
    document.getElementById("linkUsuarios").classList.remove("d-none");
    document.getElementById("linkDestinatarios").classList.remove("d-none");
  }
  if (perfil === "ADMIN" || perfil === "SUPERVISOR") {
    document.getElementById("linkMaquinas").classList.remove("d-none");
    document.getElementById("linkPecas").classList.remove("d-none");
  }

  const params = new URLSearchParams(window.location.search);
  const idParaEditar = params.get("editar");
  const idParaRascunho = params.get("rascunho");

  if (idParaEditar) {
    if (perfil !== "ADMIN" && perfil !== "SUPERVISOR") {
      alert("Apenas administradores e supervisores podem corrigir um turno já fechado.");
      window.location.href = "historico.html";
      return;
    }
    turnoEditandoId = idParaEditar;
    ativarModoEdicao();
  } else if (idParaRascunho) {
    rascunhoTurnoId = idParaRascunho;
  }

  document.getElementById("dataTurno").valueAsDate = new Date();
  atualizarRelogio();
  setInterval(atualizarRelogio, 30000);

  await Promise.all([carregarMaquinas(), carregarPecas(), carregarOrdensProducao()]);

  if (turnoEditandoId) {
    await carregarTurnoParaEdicao(turnoEditandoId);
  } else if (rascunhoTurnoId) {
    await carregarTurnoParaEdicao(rascunhoTurnoId);
  }

  // Reavalia o preenchimento automático de início/fim para a injetora
  // ativa - carregarTurnoParaEdicao só roda depois de selecionarMaquina
  // já ter preenchido os campos com o horário padrão do turno, então
  // sem isso os campos ficariam com um horário "fantasma" mesmo já
  // havendo lançamentos reais carregados para aquela injetora.
  aplicarHorarioPadraoOuLimpar();

  renderizarListaLancamentos();
  atualizarResumoTurno();
});

function ativarModoEdicao() {
  const aviso = document.createElement("div");
  aviso.className = "alert alert-warning mb-3";
  aviso.innerHTML =
    '<i class="bi bi-pencil-square me-2"></i>Você está corrigindo um turno já fechado.';
  document.querySelector(".container-fluid").prepend(aviso);
}

function atualizarRelogio() {
  const agora = new Date();
  document.getElementById("relogio").innerText = agora.toLocaleTimeString("pt-BR", {
    hour: "2-digit",
    minute: "2-digit",
  });
}

async function carregarPecas() {
  try {
    const res = await chamarApi("/produtos/");
    if (!res.ok) throw new Error("Não foi possível carregar as peças.");
    pecasDisponiveis = await res.json();
    const datalist = document.getElementById("listaPecasDatalist");
    pecasDisponiveis.forEach((p) => {
      const option = document.createElement("option");
      option.value = `${p.codigo} - ${p.descricao}`;
      datalist.appendChild(option);
    });

    // Resolve o texto digitado/selecionado no campo de busca para o
    // produto_id correspondente (campo oculto usado no restante do
    // código) - permite filtrar por código ou descrição em vez de
    // rolar uma lista longa, importante conforme o catálogo cresce.
    document.getElementById("lancPecaBusca").addEventListener("input", (evento) => {
      const peca = pecasDisponiveis.find(
        (p) => `${p.codigo} - ${p.descricao}` === evento.target.value,
      );
      document.getElementById("lancPeca").value = peca ? peca.id : "";

      const dica = document.getElementById("dicaCicloPadrao");
      dica.innerText = peca && peca.ciclo_padrao
        ? `Ciclo padrão cadastrado na peça: ${peca.ciclo_padrao}s`
        : "";
    });
  } catch (erro) {
    console.error(erro);
    pecasDisponiveis = [];
  }
}

async function carregarOrdensProducao() {
  try {
    const res = await chamarApi("/ordens-producao/");
    if (!res.ok) throw new Error("Não foi possível carregar as ordens de produção.");
    ordensProducaoDisponiveis = await res.json();
    const select = document.getElementById("lancOp");
    ordensProducaoDisponiveis.forEach((o) => {
      const option = document.createElement("option");
      option.value = o.id;
      option.textContent = `${o.numero_op}${o.produto_descricao ? " - " + o.produto_descricao : ""}`;
      select.appendChild(option);
    });
  } catch (erro) {
    console.error(erro);
    ordensProducaoDisponiveis = [];
  }
}

async function carregarMaquinas() {
  const container = document.getElementById("pills-maquinas");
  try {
    const res = await chamarApi("/maquinas/?incluir_inativas=false");
    if (!res.ok) throw new Error("Não foi possível carregar as máquinas.");
    maquinasDisponiveis = await res.json();

    if (maquinasDisponiveis.length === 0) {
      container.innerHTML = `<li class="nav-item"><span class="nav-link disabled">
        Nenhuma injetora cadastrada. Peça a um admin para cadastrar em "Máquinas".
      </span></li>`;
      return;
    }

    maquinasDisponiveis.forEach((m) => {
      if (!lancamentosState[m.numero_maquina]) {
        lancamentosState[m.numero_maquina] = [];
      }
    });

    renderizarAbasMaquinas();
    selecionarMaquina(maquinasDisponiveis[0].numero_maquina);
  } catch (erro) {
    console.error(erro);
    container.innerHTML = `<li class="nav-item"><span class="nav-link disabled text-danger">
      Erro ao carregar máquinas: ${erro.message}
    </span></li>`;
  }
}

function renderizarAbasMaquinas() {
  const container = document.getElementById("pills-maquinas");
  container.innerHTML = "";

  maquinasDisponiveis.forEach((m) => {
    const li = document.createElement("li");
    li.className = "nav-item";
    const btn = document.createElement("button");
    btn.className = "nav-link btn-maq";
    btn.dataset.numeroMaquina = m.numero_maquina;
    const rotulo = m.descricao ? `Injetora ${m.numero_maquina}` : `Máquina ${m.numero_maquina}`;
    const qtdLancamentos = (lancamentosState[m.numero_maquina] || []).length;
    btn.innerHTML = qtdLancamentos > 0 ? `${rotulo} <span class="badge bg-light text-dark ms-1">${qtdLancamentos}</span>` : rotulo;
    btn.addEventListener("click", () => selecionarMaquina(m.numero_maquina));
    li.appendChild(btn);
    container.appendChild(li);
  });

  // Reaplica a seleção visual (renderizarAbasMaquinas recria os botões
  // do zero, perdendo a classe "active" anterior).
  if (maquinaAtiva) {
    document.querySelectorAll(".btn-maq").forEach((btn) => {
      btn.classList.toggle("active", btn.dataset.numeroMaquina === maquinaAtiva);
    });
  }
}

// Horário padrão de cada turno (mesmo texto das opções do seletor) -
// usado para pré-preencher início/fim do primeiro lançamento de cada
// injetora. Turnos que atravessam a meia-noite (3º) já são tratados
// corretamente pelo cálculo de duração existente (fim < início =
// atravessa o dia), então não precisa de tratamento especial aqui.
const HORARIO_PADRAO_TURNO = {
  "1": { inicio: "05:00", fim: "13:00" },
  "2": { inicio: "14:00", fim: "21:00" },
  "3": { inicio: "22:00", fim: "04:00" },
};

// Preenche início/fim da produção com o horário padrão do turno - só
// quando essa injetora ainda não tem nenhum lançamento no turno atual.
// A partir do segundo lançamento (mesma peça retomada após uma parada,
// ou peça diferente), os campos ficam em branco de propósito: nenhum
// lançamento depois do primeiro pode ocupar o turno inteiro, então
// exigir digitação manual evita deixar por engano o horário cheio
// num lançamento que na verdade é só uma fração do turno.
function aplicarHorarioPadraoOuLimpar() {
  const campoInicio = document.getElementById("lancInicio");
  const campoFim = document.getElementById("lancFim");
  if (!campoInicio || !campoFim || !maquinaAtiva) return;

  const semLancamentoAinda = (lancamentosState[maquinaAtiva] || []).length === 0;
  if (semLancamentoAinda) {
    const turno = HORARIO_PADRAO_TURNO[document.getElementById("selectTurno").value];
    campoInicio.value = turno ? turno.inicio : "";
    campoFim.value = turno ? turno.fim : "";
  } else {
    campoInicio.value = "";
    campoFim.value = "";
  }
}

function selecionarMaquina(numeroMaquina) {
  maquinaAtiva = numeroMaquina;
  cancelarEdicaoLancamento(); // evita confusão de estar editando um lançamento de outra injetora
  document.querySelectorAll(".btn-maq").forEach((btn) => {
    btn.classList.toggle("active", btn.dataset.numeroMaquina === numeroMaquina);
  });

  const info = maquinasDisponiveis.find((m) => m.numero_maquina === numeroMaquina);
  if (info) {
    document.getElementById("tituloMaquina").innerText =
      info.descricao || `Injetora ${info.numero_maquina}`;
    const badge = document.getElementById("badgeDetalheMaquina");
    badge.innerText = info.cavidades && info.ciclo_padrao
      ? `Cavidades: ${info.cavidades} | Ciclo: ${info.ciclo_padrao}s (padrão da máquina)`
      : "Sem cavidades/ciclo padrão na máquina - use o cadastro da peça";
  }

  aplicarHorarioPadraoOuLimpar();
  renderizarListaLancamentos();
}

function onTipoLancamentoMudou() {
  const tipo = document.querySelector('input[name="tipoLancamento"]:checked').value;
  document.getElementById("camposProducao").classList.toggle("d-none", tipo !== "PRODUCAO");
  document.getElementById("camposParada").classList.toggle("d-none", tipo === "PRODUCAO");
}

function adicionarLancamento() {
  const tipo = document.querySelector('input[name="tipoLancamento"]:checked').value;

  let lancamento;
  if (tipo === "PRODUCAO") {
    const pecaId = document.getElementById("lancPeca").value;
    const quantidade = document.getElementById("lancQuantidade").value;
    const ciclo = document.getElementById("lancCiclo").value;
    const inicio = document.getElementById("lancInicio").value;
    const fim = document.getElementById("lancFim").value;

    if (!pecaId) return alert("Selecione a peça produzida.");
    if (quantidade === "" || quantidade === null) return alert("Informe a quantidade produzida.");
    if (!inicio || !fim) return alert("Informe o horário de início e fim.");
    if (fim === inicio) return alert("O horário de fim não pode ser igual ao início.");

    lancamento = {
      tipo: "PRODUCAO",
      horario_inicio: inicio,
      horario_fim: fim,
      produto_id: parseInt(pecaId),
      ordem_producao_id: document.getElementById("lancOp").value
        ? parseInt(document.getElementById("lancOp").value)
        : null,
      quantidade: parseInt(quantidade),
      ciclo_informado: ciclo !== "" ? parseFloat(ciclo) : null,
      motivo: null,
    };

    document.getElementById("lancQuantidade").value = "";
    document.getElementById("lancCiclo").value = "";
    document.getElementById("dicaCicloPadrao").innerText = "";
    document.getElementById("lancInicio").value = "";
    document.getElementById("lancFim").value = "";
    document.getElementById("lancPecaBusca").value = "";
    document.getElementById("lancPeca").value = "";
  } else {
    const inicio = document.getElementById("lancInicioParada").value;
    const fim = document.getElementById("lancFimParada").value;
    if (!inicio || !fim) return alert("Informe o horário de início e fim da parada.");
    if (fim === inicio) return alert("O horário de fim não pode ser igual ao início.");

    lancamento = {
      tipo,
      horario_inicio: inicio,
      horario_fim: fim,
      produto_id: null,
      ordem_producao_id: null,
      quantidade: null,
      ciclo_informado: null,
      motivo: document.getElementById("lancMotivo").value.trim() || null,
    };

    document.getElementById("lancMotivo").value = "";
    document.getElementById("lancInicioParada").value = "";
    document.getElementById("lancFimParada").value = "";
  }

  if (indiceEditando !== null) {
    lancamentosState[maquinaAtiva][indiceEditando] = lancamento;
    cancelarEdicaoLancamento();
  } else {
    lancamentosState[maquinaAtiva].push(lancamento);
  }

  renderizarAbasMaquinas();
  renderizarListaLancamentos();
  atualizarResumoTurno();
}

// Preenche o formulário com os dados de um lançamento já adicionado,
// para corrigir um erro de cadastro sem precisar apagar e lançar de
// novo do zero. "Adicionar Lançamento" vira "Salvar Alteração"
// enquanto a edição está em andamento.
function editarLancamento(indice) {
  const lanc = lancamentosState[maquinaAtiva][indice];
  indiceEditando = indice;

  document.getElementById(`tipo${lanc.tipo === "PRODUCAO" ? "Producao" : lanc.tipo === "PARADA_PROGRAMADA" ? "ParadaProgramada" : "ParadaFalha"}`).checked = true;
  onTipoLancamentoMudou();

  if (lanc.tipo === "PRODUCAO") {
    const peca = pecasDisponiveis.find((p) => String(p.id) === String(lanc.produto_id));
    document.getElementById("lancPecaBusca").value = peca ? `${peca.codigo} - ${peca.descricao}` : "";
    document.getElementById("lancPeca").value = lanc.produto_id;
    document.getElementById("dicaCicloPadrao").innerText = peca && peca.ciclo_padrao
      ? `Ciclo padrão cadastrado na peça: ${peca.ciclo_padrao}s`
      : "";
    document.getElementById("lancOp").value = lanc.ordem_producao_id || "";
    document.getElementById("lancQuantidade").value = lanc.quantidade;
    document.getElementById("lancCiclo").value = lanc.ciclo_informado ?? "";
    document.getElementById("lancInicio").value = lanc.horario_inicio;
    document.getElementById("lancFim").value = lanc.horario_fim;
  } else {
    document.getElementById("lancMotivo").value = lanc.motivo || "";
    document.getElementById("lancInicioParada").value = lanc.horario_inicio;
    document.getElementById("lancFimParada").value = lanc.horario_fim;
  }

  const btn = document.getElementById("btnAdicionarLancamento");
  btn.innerHTML = `<i class="bi bi-check-circle me-1"></i>Salvar Alteração`;
  btn.classList.replace("btn-primary", "btn-warning");
  document.getElementById("btnCancelarEdicaoLancamento").classList.remove("d-none");

  document.getElementById("cardNovoLancamento").scrollIntoView({ behavior: "smooth", block: "center" });
}

function cancelarEdicaoLancamento() {
  indiceEditando = null;
  const btn = document.getElementById("btnAdicionarLancamento");
  btn.innerHTML = `<i class="bi bi-plus-circle me-1"></i>Adicionar Lançamento`;
  btn.classList.replace("btn-warning", "btn-primary");
  document.getElementById("btnCancelarEdicaoLancamento").classList.add("d-none");
}

function removerLancamento(indice) {
  lancamentosState[maquinaAtiva].splice(indice, 1);
  if (indiceEditando === indice) cancelarEdicaoLancamento();
  renderizarAbasMaquinas();
  renderizarListaLancamentos();
  atualizarResumoTurno();
}

function calcularEsperadoLancamento(lanc, maquina) {
  if (lanc.tipo !== "PRODUCAO") return 0;
  const peca = lanc.produto_id
    ? pecasDisponiveis.find((p) => String(p.id) === String(lanc.produto_id))
    : null;
  // Ciclo informado manualmente (campo editável, comparado ao padrão da
  // peça) tem prioridade máxima - mesma lógica do backend.
  const ciclo = lanc.ciclo_informado || peca?.ciclo_padrao || maquina?.ciclo_padrao;
  const cavidades = peca?.cavidades || maquina?.cavidades;
  if (!ciclo || !cavidades) return 0;

  const [hIni, mIni] = lanc.horario_inicio.split(":").map(Number);
  const [hFim, mFim] = lanc.horario_fim.split(":").map(Number);
  const inicioSeg = hIni * 3600 + mIni * 60;
  let fimSeg = hFim * 3600 + mFim * 60;
  // Fim menor ou igual ao início = atravessa a meia-noite (3º turno,
  // ex.: 22:00 até 05:00 do dia seguinte) - soma 24h ao horário final,
  // mesma lógica do backend (ver analytics.py:_duracao_segundos).
  if (fimSeg <= inicioSeg) fimSeg += 24 * 3600;
  const duracaoSeg = fimSeg - inicioSeg;
  return Math.round((duracaoSeg / ciclo) * cavidades);
}

function renderizarListaLancamentos() {
  const tbody = document.getElementById("corpoListaLancamentos");
  const lista = lancamentosState[maquinaAtiva] || [];
  const maquina = maquinasDisponiveis.find((m) => m.numero_maquina === maquinaAtiva);

  if (lista.length === 0) {
    tbody.innerHTML = `<tr><td colspan="9" class="text-center text-secondary py-3">Nenhum lançamento ainda nesta injetora.</td></tr>`;
    return;
  }

  const rotuloTipo = {
    PRODUCAO: '<span class="badge bg-success">Produção</span>',
    PARADA_PROGRAMADA: '<span class="badge bg-warning text-dark">Parada Programada</span>',
    PARADA_FALHA: '<span class="badge bg-danger">Falha</span>',
  };

  tbody.innerHTML = lista
    .map((lanc, i) => {
      const peca = lanc.produto_id
        ? pecasDisponiveis.find((p) => String(p.id) === String(lanc.produto_id))
        : null;
      const op = lanc.ordem_producao_id
        ? ordensProducaoDisponiveis.find((o) => String(o.id) === String(lanc.ordem_producao_id))
        : null;
      const pecaOuMotivo = lanc.tipo === "PRODUCAO" ? (peca?.descricao || "-") : (lanc.motivo || "-");
      const esperado = calcularEsperadoLancamento(lanc, maquina);

      // Ciclo real informado x ciclo padrão da peça, lado a lado - o
      // líder de turno pediu essa comparação para identificar quando o
      // molde está regulado diferente do cadastrado.
      let ciclos = "-";
      if (lanc.tipo === "PRODUCAO") {
        const informado = lanc.ciclo_informado ? `${lanc.ciclo_informado}s` : "-";
        const padrao = peca?.ciclo_padrao ? `${peca.ciclo_padrao}s` : "-";
        const divergente = lanc.ciclo_informado && peca?.ciclo_padrao
          && Math.abs(lanc.ciclo_informado - peca.ciclo_padrao) > 0.05;
        ciclos = `<span class="${divergente ? 'text-danger fw-bold' : ''}">${informado}</span> <span class="text-secondary">(${padrao})</span>`;
      }

      const emEdicao = i === indiceEditando;

      return `
        <tr class="${emEdicao ? 'table-warning' : ''}">
          <td>${rotuloTipo[lanc.tipo]}</td>
          <td>${lanc.horario_inicio}</td>
          <td>${lanc.horario_fim}</td>
          <td>${escaparHtml(pecaOuMotivo)}</td>
          <td>${op ? escaparHtml(op.numero_op) : "-"}</td>
          <td class="text-center">${lanc.quantidade ?? "-"}</td>
          <td class="text-center">${ciclos}</td>
          <td class="text-center">${lanc.tipo === "PRODUCAO" ? esperado : "-"}</td>
          <td class="text-center">
            <div class="d-flex gap-1 justify-content-center">
              <button class="btn btn-sm btn-outline-secondary" onclick="editarLancamento(${i})" title="Corrigir">
                <i class="bi bi-pencil-square"></i>
              </button>
              <button class="btn btn-sm btn-outline-danger" onclick="removerLancamento(${i})" title="Excluir">
                <i class="bi bi-trash"></i>
              </button>
            </div>
          </td>
        </tr>
      `;
    })
    .join("");
}

function atualizarResumoTurno() {
  let totalEsperado = 0;
  let totalApontado = 0;

  maquinasDisponiveis.forEach((maquina) => {
    (lancamentosState[maquina.numero_maquina] || []).forEach((lanc) => {
      if (lanc.tipo === "PRODUCAO") {
        totalApontado += lanc.quantidade || 0;
        totalEsperado += calcularEsperadoLancamento(lanc, maquina);
      }
    });
  });

  document.getElementById("resumoEsperado").innerText = totalEsperado.toLocaleString("pt-BR");
  document.getElementById("resumoApontado").innerText = totalApontado.toLocaleString("pt-BR");

  const percEl = document.getElementById("resumoPercentual");
  if (totalEsperado > 0) {
    const percentual = Math.round((totalApontado / totalEsperado) * 100);
    percEl.innerText = `${percentual}%`;
    percEl.className = `fs-4 fw-bold ${percentual >= 90 ? "text-success" : percentual >= 60 ? "text-warning" : "text-danger"}`;
  } else {
    percEl.innerText = "-";
    percEl.className = "fs-4 fw-bold text-secondary";
  }
}

async function carregarTurnoParaEdicao(turnoId) {
  try {
    const res = await chamarApi(`/turnos/${turnoId}`);
    if (!res.ok) throw new Error("Turno não encontrado.");
    const turno = await res.json();

    const selectTurno = document.getElementById("selectTurno");
    for (const opcao of selectTurno.options) {
      if (opcao.text === turno.nome_turno) {
        selectTurno.value = opcao.value;
        break;
      }
    }

    document.getElementById("nomeLider").value = turno.responsavel_nome || "";
    document.getElementById("nomeRegulador").value = turno.regulador_nome || "";
    document.getElementById("observacoesTurno").value = turno.observacoes || "";

    (turno.lancamentos || []).forEach((lanc) => {
      if (!lancamentosState[lanc.numero_maquina]) {
        lancamentosState[lanc.numero_maquina] = [];
      }
      lancamentosState[lanc.numero_maquina].push({
        tipo: lanc.tipo,
        horario_inicio: lanc.horario_inicio,
        horario_fim: lanc.horario_fim,
        produto_id: lanc.produto_id,
        ordem_producao_id: lanc.ordem_producao_id,
        quantidade: lanc.quantidade,
        ciclo_informado: lanc.ciclo_informado,
        motivo: lanc.motivo,
      });
    });

    renderizarAbasMaquinas();
  } catch (erro) {
    console.error(erro);
    alert("Não foi possível carregar o turno para edição.");
  }
}

function montarPayloadFechamento() {
  const lider = document.getElementById("nomeLider").value.trim();
  const regulador = document.getElementById("nomeRegulador").value.trim();
  const turnoSelect = document.getElementById("selectTurno");
  const payload = {
    nome_turno: turnoSelect.options[turnoSelect.selectedIndex].text,
    responsavel_nome: lider,
    regulador_nome: regulador || null,
    observacoes: document.getElementById("observacoesTurno").value,
    lancamentos: [],
  };

  maquinasDisponiveis.forEach((m) => {
    (lancamentosState[m.numero_maquina] || []).forEach((lanc) => {
      payload.lancamentos.push({ numero_maquina: m.numero_maquina, ...lanc });
    });
  });

  return { lider, payload };
}

async function confirmarFechamento() {
  const { lider, payload } = montarPayloadFechamento();
  if (!lider) return alert("Por favor, preencha o nome do líder antes de finalizar.");
  if (payload.lancamentos.length === 0) {
    return alert("Adicione pelo menos um lançamento (produção ou parada) antes de finalizar.");
  }

  let caminho, metodo, tipo;
  if (turnoEditandoId) {
    caminho = `/turnos/lancamento/${turnoEditandoId}`;
    metodo = "PATCH";
    tipo = "correcao";
  } else if (rascunhoTurnoId) {
    caminho = `/turnos/lancamento/${rascunhoTurnoId}/fechar`;
    metodo = "POST";
    tipo = "fechar_rascunho";
  } else {
    caminho = `/turnos/lancamento`;
    metodo = "POST";
    tipo = "fechar_direto";
  }

  try {
    const res = await chamarApi(caminho, { method: metodo, body: JSON.stringify(payload) });

    if (res.status === 403) {
      alert("Você não tem permissão para corrigir este turno.");
      return;
    }

    if (res.ok) {
      if (tipo === "correcao") {
        alert("✅ Turno corrigido com sucesso!");
      } else {
        alert("✅ Fechamento de turno registrado e assinado com sucesso! O relatório será gerado.");
      }
      window.location.href = "historico.html";
    } else {
      const erro = await res.json().catch(() => null);
      alert("⚠️ " + (erro?.detail || "Erro ao registrar dados. Verifique a conexão com o servidor."));
    }
  } catch (error) {
    if (error.message === "Sessão expirada.") return;
    console.error("Erro na requisição:", error);
    alert("❌ Não foi possível conectar à API.");
  }
}

async function salvarRascunho() {
  const { lider, payload } = montarPayloadFechamento();
  if (!lider) return alert("Por favor, preencha o nome do líder antes de salvar o rascunho.");
  if (turnoEditandoId) {
    return alert("Este turno já está fechado - use 'Salvar Correção' em vez de rascunho.");
  }

  const btn = document.getElementById("btnSalvarRascunho");
  const textoOriginal = btn.innerHTML;
  btn.disabled = true;
  btn.innerHTML = `<span class="spinner-border spinner-border-sm"></span>`;

  const caminho = rascunhoTurnoId
    ? `/turnos/lancamento/rascunho/${rascunhoTurnoId}`
    : `/turnos/lancamento/rascunho`;
  const metodo = rascunhoTurnoId ? "PATCH" : "POST";

  try {
    const res = await chamarApi(caminho, { method: metodo, body: JSON.stringify(payload) });

    if (!res.ok) {
      const erro = await res.json().catch(() => null);
      alert("⚠️ " + (erro?.detail || "Não foi possível salvar o rascunho."));
      return;
    }

    const resultado = await res.json();
    rascunhoTurnoId = String(resultado.turno_id);

    const novaUrl = `${window.location.pathname}?rascunho=${rascunhoTurnoId}`;
    window.history.replaceState({}, "", novaUrl);

    const indicador = document.getElementById("indicadorRascunho");
    const agora = new Date().toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit" });
    indicador.innerText = `Rascunho salvo às ${agora}`;
    indicador.classList.remove("d-none");
  } catch (error) {
    if (error.message === "Sessão expirada.") return;
    console.error("Erro ao salvar rascunho:", error);
    alert("❌ Não foi possível salvar o rascunho.");
  } finally {
    btn.disabled = false;
    btn.innerHTML = textoOriginal;
  }
}

function escaparHtml(texto) {
  const div = document.createElement("div");
  div.textContent = texto;
  return div.innerHTML;
}
