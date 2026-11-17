// Funções chamadas pelos atributos data-onclick/data-onchange/data-oninput
// do HTML (ver js/acoes.js) - lista fechada, substitui os handlers inline.
registrarAcoes({ adicionarLancamento, aplicarHorarioPadraoOuLimpar, cancelarEdicaoLancamento, confirmarFechamento, editarLancamento, onTipoLancamentoMudou, removerLancamento, salvarRascunho });

// Estado: lancamentosState[numero_maquina] = [ {tipo, horario_inicio, horario_fim, produto_id, ordem_producao_id, quantidade, ciclo_informado, cavidades_informado, peso_bruto_descarte, motivo}, ... ]
// IMPORTANTE: todo campo que um lançamento pode carregar precisa
// aparecer TANTO aqui quanto no carregamento de um turno existente
// para edição (carregarLancamentoParaEdicao/buscar por id, adiante
// nesse arquivo) - um campo esquecido em só um dos dois lugares
// desaparece silenciosamente ao reeditar um turno já fechado (bug
// real, relatado pelo usuário: cavidades_informado e
// peso_bruto_descarte foram adicionados ao payload de envio, mas
// ficaram de fora da lista explícita de campos ao CARREGAR um turno
// existente para edição, então reeditar qualquer lançamento de um
// turno com descarte apagava o refugo do turno inteiro).
let lancamentosState = {};
let maquinasDisponiveis = [];
let pecasDisponiveis = [];
let ordensProducaoDisponiveis = [];
let maquinaAtiva = null;
let indiceEditando = null; // índice do lançamento sendo corrigido (dentro de lancamentosState[maquinaAtiva]), ou null se estiver adicionando um novo

let turnoEditandoId = null; // corrigir turno LANCAMENTO já fechado (ADMIN/SUPERVISOR)
let rascunhoTurnoId = null; // continuar um rascunho LANCAMENTO em andamento

let usuarioLogado = null; // { id, nome, perfil } - dono dos turnos enviados/enfileirados
let cadastrosDoAparelho = null; // data da cópia local dos cadastros, se a tela abriu sem conexão
let idEnvioFechamento = null; // UUID do fechamento (mesmo em novas tentativas -> servidor não duplica)
let fechadoEmISO = null; // quando o operador tocou em "Finalizar"

document.addEventListener("DOMContentLoaded", async () => {
  // permitirOffline: sem sinal, abre com a última sessão conhecida neste aparelho.
  const sessao = await exigirSessao({ permitirOffline: true });
  if (!sessao) return;
  usuarioLogado = sessao;

  const perfil = sessao.perfil;
  if (perfil === "ADMIN") {
    document.getElementById("linkUsuarios").classList.remove("d-none");
    document.getElementById("linkDestinatarios").classList.remove("d-none");
    document.getElementById("linkPecas").classList.remove("d-none");
    document.getElementById("linkOrdensProducao").classList.remove("d-none");
  }
  if (perfil === "ADMIN" || perfil === "SUPERVISOR") {
    document.getElementById("linkMaquinas").classList.remove("d-none");
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
  avisarCadastrosDoAparelho();

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

// Busca um cadastro na API e guarda uma cópia no aparelho. Se a API não
// responder (sem sinal, servidor acordando), usa a última cópia guardada,
// para o apontamento poder ser preenchido offline. Sessão expirada (401)
// continua levando ao login, sem usar cópia.
async function buscarCadastro(chave, caminho, mensagemErro) {
  try {
    const res = await chamarApi(caminho);
    if (!res.ok) throw new Error(mensagemErro);
    const dados = await res.json();
    if (window.FilaOffline) window.FilaOffline.salvarCatalogo(chave, dados);
    return dados;
  } catch (erro) {
    if (erro.message === "Sessão expirada.") throw erro;
    const copia = window.FilaOffline ? await window.FilaOffline.lerCatalogo(chave) : null;
    if (copia && Array.isArray(copia.dados)) {
      if (!cadastrosDoAparelho || copia.salvo_em < cadastrosDoAparelho) {
        cadastrosDoAparelho = copia.salvo_em;
      }
      return copia.dados;
    }
    throw erro;
  }
}

function avisarCadastrosDoAparelho() {
  if (!cadastrosDoAparelho) return;
  const quando = new Date(cadastrosDoAparelho).toLocaleString("pt-BR", {
    day: "2-digit",
    month: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
  const aviso = document.createElement("div");
  aviso.className = "alert alert-warning mb-3";
  aviso.textContent =
    "Sem conexão: máquinas, peças e ordens de produção vieram da cópia guardada neste aparelho (" +
    quando +
    "). Você pode preencher e finalizar o turno; ele será enviado quando o sinal voltar.";
  document.querySelector(".container-fluid").prepend(aviso);
}

async function carregarPecas() {
  try {
    pecasDisponiveis = await buscarCadastro("produtos", "/produtos/", "Não foi possível carregar as peças.");
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

      const dicaCavidades = document.getElementById("dicaCavidadesPadrao");
      dicaCavidades.innerText = peca && peca.cavidades
        ? `Cavidades cadastradas na peça: ${peca.cavidades}`
        : "";

      const dicaPeso = document.getElementById("dicaPesoPeca");
      dicaPeso.innerText = peca && peca.peso_gramas
        ? `Peso cadastrado na peça: ${peca.peso_gramas}g`
        : "";

      atualizarDicaRefugo();
    });

    document.getElementById("lancPesoDescarte").addEventListener("input", atualizarDicaRefugo);
  } catch (erro) {
    console.error(erro);
    pecasDisponiveis = [];
  }
}

async function carregarOrdensProducao() {
  try {
    ordensProducaoDisponiveis = await buscarCadastro(
      "ordens",
      "/ordens-producao/",
      "Não foi possível carregar as ordens de produção.",
    );
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
    maquinasDisponiveis = await buscarCadastro(
      "maquinas",
      "/maquinas/?incluir_inativas=false",
      "Não foi possível carregar as máquinas.",
    );

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
      Erro ao carregar máquinas: ${escaparHtml(erro.message)}
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
    // textContent (não innerHTML): numero_maquina é texto livre cadastrado
    // por ADMIN/SUPERVISOR e não pode ser interpretado como HTML.
    btn.textContent = rotulo;
    if (qtdLancamentos > 0) {
      const badge = document.createElement("span");
      badge.className = "badge bg-light text-dark ms-1";
      badge.textContent = String(qtdLancamentos);
      btn.appendChild(badge);
    }
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
// injetora. IMPORTANTE: existe de propósito uma lacuna de 60min entre
// o fim de um turno e o início do próximo (13:00→14:00, 21:00→22:00,
// 04:00→05:00) - confirmado com a empresa que esse intervalo é usado
// para manutenção, troca de molde e troca de matéria-prima da
// injetora, não é falha de agenda nem tempo "perdido" para preencher.
// Não "consertar" isso fechando a lacuna - já foi tentado antes e
// revertido a pedido da empresa. Turno que atravessa a meia-noite (3º)
// já é tratado corretamente pelo cálculo de duração existente (fim <
// início = atravessa o dia), então não precisa de tratamento especial
// aqui.
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
  atualizarAvisoTurnoNoturno();

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

// Mostra um lembrete quando o 3º Turno é selecionado - esse único
// turno atravessa a meia-noite (22:00 - 04:00), o que já causou
// confusão real (turno fechado de madrugada registrado com a data do
// fechamento em vez da data em que começou). O backend já calcula a
// data certa sozinho a partir do horário dos lançamentos (não depende
// do campo Data, que é só uma referência visual pro operador) - esse
// aviso é só para reduzir a chance de o operador ficar em dúvida ou
// preencher o campo Data de um jeito que pareça inconsistente com o
// que vai aparecer no relatório depois.
function atualizarAvisoTurnoNoturno() {
  const aviso = document.getElementById("avisoTurnoNoturno");
  if (!aviso) return;
  const turnoSelecionado = document.getElementById("selectTurno").value;
  aviso.classList.toggle("d-none", turnoSelecionado !== "3");
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
  // camposProducaoLinha2 (Ciclo real/Cavidades usadas/Início/Fim)
  // nunca era escondida - bug real reportado pelo usuário: ao
  // selecionar Parada Programada ou Falha na Injetora, esses campos
  // (não usados por esses dois tipos, ver adicionarLancamento())
  // continuavam visíveis ao lado dos campos corretos (Motivo/Início/
  // Fim de camposParada), dando a impressão de início/fim duplicados
  // na tela.
  document.getElementById("camposProducaoLinha2").classList.toggle("d-none", tipo !== "PRODUCAO");
  document.getElementById("camposParada").classList.toggle("d-none", tipo === "PRODUCAO");
}

function adicionarLancamento() {
  const tipo = document.querySelector('input[name="tipoLancamento"]:checked').value;

  let lancamento;
  if (tipo === "PRODUCAO") {
    const pecaId = document.getElementById("lancPeca").value;
    const quantidade = document.getElementById("lancQuantidade").value;
    const ciclo = document.getElementById("lancCiclo").value;
    const cavidades = document.getElementById("lancCavidades").value;
    const pesoDescarte = document.getElementById("lancPesoDescarte").value;
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
      cavidades_informado: cavidades !== "" ? parseInt(cavidades) : null,
      peso_bruto_descarte: pesoDescarte !== "" ? parseFloat(pesoDescarte) : null,
      motivo: null,
    };

    document.getElementById("lancQuantidade").value = "";
    document.getElementById("lancCiclo").value = "";
    document.getElementById("dicaCicloPadrao").innerText = "";
    document.getElementById("lancCavidades").value = "";
    document.getElementById("dicaCavidadesPadrao").innerText = "";
    document.getElementById("lancPesoDescarte").value = "";
    document.getElementById("dicaPesoPeca").innerText = "";
    document.getElementById("dicaRefugoEstimado").innerText = "";
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
      cavidades_informado: null,
      peso_bruto_descarte: null,
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
    document.getElementById("dicaCavidadesPadrao").innerText = peca && peca.cavidades
      ? `Cavidades cadastradas na peça: ${peca.cavidades}`
      : "";
    document.getElementById("dicaPesoPeca").innerText = peca && peca.peso_gramas
      ? `Peso cadastrado na peça: ${peca.peso_gramas}g`
      : "";
    document.getElementById("lancOp").value = lanc.ordem_producao_id || "";
    document.getElementById("lancQuantidade").value = lanc.quantidade;
    document.getElementById("lancCiclo").value = lanc.ciclo_informado ?? "";
    document.getElementById("lancCavidades").value = lanc.cavidades_informado ?? "";
    document.getElementById("lancPesoDescarte").value = lanc.peso_bruto_descarte ?? "";
    atualizarDicaRefugo();
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
  // Só o cadastro (peça, com fallback para a máquina) entra na conta -
  // mesma lógica do backend (ver analytics.calcular_capacidade_
  // esperada_lancamento). ciclo_informado/cavidades_informado NÃO
  // influenciam mais o esperado (decisão do usuário: manter o
  // "esperado" estável e comparável entre turnos, independente do que
  // foi digitado naquele lançamento específico) - continuam sendo
  // registrados e mostrados no relatório só como referência.
  const ciclo = peca?.ciclo_padrao || maquina?.ciclo_padrao;
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

// Estimativa de refugo ao vivo, mesma fórmula do backend (ver
// analytics.calcular_refugo_lancamento): refugo = peso do descarte em
// gramas ÷ peso de uma peça em gramas (campo já existente no cadastro
// da peça, "Peso (g)") - os dois lados na mesma unidade, sem
// conversão (peças pequenas podem pesar frações de grama). Chamada
// tanto ao trocar de peça quanto ao digitar o peso do descarte, para
// o número atualizar em tempo real nos dois casos.
function atualizarDicaRefugo() {
  // O peso cadastrado na peça já é mostrado assim que ela é
  // selecionada, num aviso fixo próprio (dicaPesoPeca, ao lado das
  // dicas equivalentes de ciclo/cavidades) - esta função cuida só da
  // ESTIMATIVA de refugo, calculada a partir do que foi digitado
  // aqui.
  const dica = document.getElementById("dicaRefugoEstimado");
  if (!dica) return;

  const pecaId = document.getElementById("lancPeca").value;
  const peca = pecasDisponiveis.find((p) => String(p.id) === String(pecaId));
  const pesoDescarteStr = document.getElementById("lancPesoDescarte").value;
  const pesoDescarte = parseFloat(pesoDescarteStr);

  if (!pesoDescarteStr || Number.isNaN(pesoDescarte) || pesoDescarte <= 0) {
    // Sem peso de descarte digitado ainda - não é o caso comum (a
    // maioria dos lançamentos não tem descarte nenhum), então não
    // alarma por antecipação.
    dica.innerText = "";
    return;
  }

  if (!peca || !peca.peso_gramas) {
    dica.innerText = "Peça sem peso cadastrado - não é possível estimar o refugo (cadastre o peso em Peças).";
    return;
  }

  const refugoEstimado = Math.round(pesoDescarte / peca.peso_gramas);
  dica.innerText = `Refugo estimado: ${refugoEstimado} peça(s) (${pesoDescarte}g ÷ ${peca.peso_gramas}g/peça)`;
}

function renderizarListaLancamentos() {
  const tbody = document.getElementById("corpoListaLancamentos");
  const lista = lancamentosState[maquinaAtiva] || [];
  const maquina = maquinasDisponiveis.find((m) => m.numero_maquina === maquinaAtiva);

  if (lista.length === 0) {
    tbody.innerHTML = `<tr><td colspan="10" class="text-center text-secondary py-3">Nenhum lançamento ainda nesta injetora.</td></tr>`;
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
      let cavidadesTexto = "-";
      if (lanc.tipo === "PRODUCAO") {
        const informado = lanc.ciclo_informado ? `${lanc.ciclo_informado}s` : "-";
        const padrao = peca?.ciclo_padrao ? `${peca.ciclo_padrao}s` : "-";
        const divergente = lanc.ciclo_informado && peca?.ciclo_padrao
          && Math.abs(lanc.ciclo_informado - peca.ciclo_padrao) > 0.05;
        ciclos = `<span class="${divergente ? 'text-danger fw-bold' : ''}">${informado}</span> <span class="text-secondary">(${padrao})</span>`;

        const cavidadesInformadas = lanc.cavidades_informado ?? "-";
        const cavidadesPadrao = peca?.cavidades ?? "-";
        const cavidadesDivergentes = lanc.cavidades_informado && peca?.cavidades
          && lanc.cavidades_informado !== peca.cavidades;
        cavidadesTexto = `<span class="${cavidadesDivergentes ? 'text-danger fw-bold' : ''}">${cavidadesInformadas}</span> <span class="text-secondary">(${cavidadesPadrao})</span>`;
      }

      const emEdicao = i === indiceEditando;

      return `
        <tr class="${emEdicao ? 'table-warning' : ''}">
          <td>${rotuloTipo[lanc.tipo]}</td>
          <td>${escaparHtml(lanc.horario_inicio)}</td>
          <td>${escaparHtml(lanc.horario_fim)}</td>
          <td>${escaparHtml(pecaOuMotivo)}</td>
          <td>${op ? escaparHtml(op.numero_op) : "-"}</td>
          <td class="text-center">${lanc.quantidade ?? "-"}</td>
          <td class="text-center">${ciclos}</td>
          <td class="text-center">${cavidadesTexto}</td>
          <td class="text-center">${lanc.tipo === "PRODUCAO" ? esperado : "-"}</td>
          <td class="text-center">
            <div class="d-flex gap-1 justify-content-center">
              <button class="btn btn-sm btn-outline-secondary" data-onclick="editarLancamento" data-args='[${i}]' title="Corrigir">
                <i class="bi bi-pencil-square"></i>
              </button>
              <button class="btn btn-sm btn-outline-danger" data-onclick="removerLancamento" data-args='[${i}]' title="Excluir">
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
    // Casa pelo prefixo ("1º Turno", "2º Turno"...), não pelo texto
    // inteiro - o texto completo inclui o horário entre parênteses, que
    // muda se o horário padrão do turno for atualizado no futuro (ex.:
    // correção de lacuna entre turnos). Um turno salvo antes dessa
    // mudança guarda o rótulo antigo completo em nome_turno; casar só
    // pelo prefixo continua reconhecendo de qual turno se trata mesmo
    // quando o horário exibido nas opções já é outro.
    const prefixoSalvo = (turno.nome_turno || "").split("(")[0].trim();
    for (const opcao of selectTurno.options) {
      const prefixoOpcao = opcao.text.split("(")[0].trim();
      if (prefixoOpcao === prefixoSalvo) {
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
        cavidades_informado: lanc.cavidades_informado,
        peso_bruto_descarte: lanc.peso_bruto_descarte,
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

  // Evita PDF duplicado por duplo clique - a geração do relatório
  // pode levar alguns segundos, tempo suficiente para alguém clicar
  // de novo sem perceber que a primeira requisição já está em
  // andamento. O botão só volta ao normal no fim (sucesso, erro, ou
  // exceção) - no caminho de sucesso a página normalmente navega
  // para outro lugar antes disso importar, mas reabilitar sempre é
  // mais seguro que deixar travado caso isso mude no futuro.
  const botao = document.getElementById("btnFinalizarTurno");
  const conteudoOriginal = botao.innerHTML;
  botao.disabled = true;
  botao.innerHTML = '<span class="spinner-border spinner-border-sm me-2" role="status" aria-hidden="true"></span>Gerando documento...';

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

  // Fechamentos novos (não correções) levam um id de envio: se o pedido
  // for repetido - nova tentativa, fila offline, resposta perdida - o
  // servidor devolve o turno já registrado em vez de criar outro. Também
  // levam o horário real do toque, para o turno ter a data certa mesmo se
  // o envio atrasar por falta de sinal.
  if (tipo !== "correcao") {
    if (!idEnvioFechamento) {
      idEnvioFechamento = gerarUuid();
      fechadoEmISO = new Date().toISOString();
    }
    payload.id_envio = idEnvioFechamento;
    payload.fechado_em = fechadoEmISO;
  }

  try {
    const res = await chamarApi(caminho, { method: metodo, body: JSON.stringify(payload) });

    if (res.status === 403) {
      alert("Você não tem permissão para corrigir este turno.");
      return;
    }

    if (tipo !== "correcao" && [502, 503, 504].includes(res.status)) {
      // Servidor fora do ar/acordando: trata como falta de conexão.
      if (await guardarParaEnviarDepois(caminho, metodo, payload)) return;
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
      alert("⚠️ " + extrairMensagemDeErro(erro, "Erro ao registrar dados. Verifique a conexão com o servidor."));
    }
  } catch (error) {
    if (error.message === "Sessão expirada.") return;
    console.error("Erro na requisição:", error);
    // Falha de rede (fetch sem resposta): guarda o turno para enviar
    // quando o sinal voltar. Correção de turno antigo não entra na fila.
    if (tipo !== "correcao" && (error instanceof TypeError || navigator.onLine === false)) {
      if (await guardarParaEnviarDepois(caminho, metodo, payload)) return;
    }
    alert("❌ Não foi possível conectar à API.");
  } finally {
    botao.disabled = false;
    botao.innerHTML = conteudoOriginal;
  }
}

function gerarUuid() {
  if (window.crypto && typeof window.crypto.randomUUID === "function") {
    return window.crypto.randomUUID();
  }
  // Navegador sem randomUUID (ou página fora de contexto seguro).
  const bytes = new Uint8Array(16);
  window.crypto.getRandomValues(bytes);
  bytes[6] = (bytes[6] & 0x0f) | 0x40;
  bytes[8] = (bytes[8] & 0x3f) | 0x80;
  const h = Array.from(bytes, (b) => b.toString(16).padStart(2, "0")).join("");
  return `${h.slice(0, 8)}-${h.slice(8, 12)}-${h.slice(12, 16)}-${h.slice(16, 20)}-${h.slice(20)}`;
}

// Guarda o fechamento no aparelho para envio automático depois. Só diz
// ao operador que "foi guardado" se a gravação deu certo; senão devolve
// false e o fluxo normal mostra o erro (e o turno continua na tela).
async function guardarParaEnviarDepois(caminho, metodo, payload) {
  if (!window.FilaOffline || !usuarioLogado) return false;
  try {
    await window.FilaOffline.enfileirar({
      id_envio: payload.id_envio,
      caminho,
      metodo,
      payload,
      usuario_id: usuarioLogado.id,
      usuario_nome: usuarioLogado.nome,
    });
  } catch (erro) {
    console.error("Não foi possível guardar o turno no aparelho:", erro);
    return false;
  }
  alert(
    "📴 Sem conexão com o servidor.\n\nO turno foi guardado neste aparelho e será enviado " +
      "automaticamente quando o sinal voltar. Não é preciso refazer.",
  );
  window.location.href = "home.html";
  return true;
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
      alert("⚠️ " + extrairMensagemDeErro(erro, "Não foi possível salvar o rascunho."));
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
    if (error instanceof TypeError || navigator.onLine === false) {
      alert(
        "📴 Sem conexão: o rascunho não foi salvo. Você pode continuar preenchendo e finalizar o turno - " +
          "ele será guardado neste aparelho e enviado quando o sinal voltar.",
      );
    } else {
      alert("❌ Não foi possível salvar o rascunho.");
    }
  } finally {
    btn.disabled = false;
    btn.innerHTML = textoOriginal;
  }
}

function escaparHtml(texto) {
  // .textContent + .innerHTML escapa <, > e & corretamente para uso
  // como texto/innerHTML - mas NÃO aspas, que só importam quando o
  // valor é interpolado dentro de um atributo HTML (ex.: value="...").
  // Escapadas aqui também, como reforço geral - mesmo que o padrão
  // preferido do projeto seja não interpolar em atributo nenhum
  // (setar .value via API do DOM em vez disso), essa função pode vir
  // a ser usada assim por engano no futuro, e sem isso o escape
  // ficaria incompleto silenciosamente (achado numa avaliação de
  // segurança - ver commit que corrigiu apontamento_horario.js).
  const div = document.createElement("div");
  div.textContent = texto;
  return div.innerHTML.replaceAll('"', "&quot;").replaceAll("'", "&#39;");
}
