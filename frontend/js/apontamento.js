// Grade horária de acordo com as fichas operacionais de cada turno
const HORARIOS_POR_TURNO = {
  1: [
    "05:00",
    "06:00",
    "07:00",
    "08:00",
    "09:00",
    "10:00",
    "11:00",
    "12:00",
    "13:00",
  ],
  2: ["14:00", "15:00", "16:00", "17:00", "18:00", "19:00", "20:00", "21:00"],
  3: ["22:00", "23:00", "00:00", "01:00", "02:00", "03:00", "04:00"],
};

// Lista de máquinas (ativas, ou todas se estiver editando um turno antigo).
// Cada item: { id, numero_maquina, descricao, cavidades, ciclo_padrao }
let maquinasDisponiveis = [];
let maquinaAtiva = null; // guarda o numero_maquina (string) selecionado
// Catálogo de peças (GET /produtos/): { id, codigo, descricao, ciclo_padrao, cavidades }
let pecasDisponiveis = [];
// Ordens de Produção cadastradas (GET /ordens-producao/): { id, numero_op, produto_descricao, ... }
let ordensProducaoDisponiveis = [];
// Estado centralizado dos apontamentos: dados[numero_maquina][hora] = { prod, inicio, retomada, motivo, produtoId, ordemProducaoId, paradaProgramada, cicloInformado, contadorParada, contadorRetomada }
let registrosState = {};

// Preenchido quando a tela está em modo de correção de um turno já
// fechado (via apontamento.html?editar=<id>). null = modo normal (novo turno).
let turnoEditandoId = null;

// Inicialização
document.addEventListener("DOMContentLoaded", async () => {
  // Sem sessão válida, manda direto pra tela de login.
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

  if (idParaEditar) {
    if (perfil !== "ADMIN" && perfil !== "SUPERVISOR") {
      alert(
        "Apenas administradores e supervisores podem corrigir um turno já fechado.",
      );
      window.location.href = "historico.html";
      return;
    }
    turnoEditandoId = idParaEditar;
    ativarModoEdicao();
  }

  document.getElementById("dataTurno").valueAsDate = new Date();
  atualizarRelogio();
  setInterval(atualizarRelogio, 1000);

  // Em modo de edição, inclui também máquinas já desativadas, para que
  // os registros históricos delas continuem visíveis e editáveis.
  await Promise.all([
    carregarMaquinas(!!turnoEditandoId),
    carregarPecas(),
    carregarOrdensProducao(),
  ]);

  if (turnoEditandoId) {
    await carregarTurnoParaEdicao(turnoEditandoId);
  }

  renderizarTabela();
});

function ativarModoEdicao() {
  const aviso = document.createElement("div");
  aviso.className =
    "alert alert-warning d-flex justify-content-between align-items-center mb-3";
  aviso.innerHTML = `
    <span><i class="bi bi-pencil-square me-2"></i>Corrigindo um turno já encerrado.</span>
    <a href="historico.html" class="btn btn-sm btn-outline-dark">Cancelar</a>
  `;
  document.querySelector(".container-fluid.p-3").prepend(aviso);

  const botaoFechar = document.querySelector(
    'button[onclick="confirmarFechamento()"]',
  );
  botaoFechar.innerHTML =
    '<i class="bi bi-check-circle me-2"></i>Salvar Correção';

  // O turno (1º/2º/3º) não é editável em modo de correção, para evitar
  // inconsistência entre a grade de horários e os registros já salvos.
  document.getElementById("selectTurno").disabled = true;
}

async function carregarTurnoParaEdicao(turnoId) {
  try {
    const res = await chamarApi(`/turnos/${turnoId}`);

    if (!res.ok) throw new Error("Turno não encontrado.");

    const turno = await res.json();

    // Tenta casar o nome_turno salvo com uma das opções do seletor
    // (ex.: "1º Turno (05:00 - 13:00)") para pré-selecionar a grade
    // horária correta.
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

    turno.registros.forEach((reg) => {
      if (!registrosState[reg.numero_maquina]) {
        registrosState[reg.numero_maquina] = {};
      }
      registrosState[reg.numero_maquina][reg.hora_referencia] = {
        prod: reg.prod_executada ?? "",
        inicio: reg.inicio_parada ? reg.inicio_parada.slice(0, 5) : "",
        retomada: reg.retomada ? reg.retomada.slice(0, 5) : "",
        motivo: reg.motivo_parada || "",
        produtoId: reg.produto_id ?? "",
        ordemProducaoId: reg.ordem_producao_id ?? "",
        paradaProgramada: !!reg.parada_programada,
        cicloInformado: reg.ciclo_informado ?? "",
        contadorParada: reg.contador_parada ?? "",
        contadorRetomada: reg.contador_retomada ?? "",
      };
    });
  } catch (erro) {
    console.error(erro);
    alert("Não foi possível carregar os dados do turno para edição.");
    window.location.href = "historico.html";
  }
}

async function carregarPecas() {
  try {
    const res = await chamarApi("/produtos/");
    if (!res.ok) throw new Error("Não foi possível carregar as peças.");
    pecasDisponiveis = await res.json();
  } catch (erro) {
    console.error(erro);
    // Não bloqueia o apontamento: sem o catálogo carregado, o seletor de
    // peça fica só com a opção em branco, mas o resto da tela funciona.
    pecasDisponiveis = [];
  }
}

async function carregarOrdensProducao() {
  try {
    const res = await chamarApi("/ordens-producao/");
    if (!res.ok) throw new Error("Não foi possível carregar as ordens de produção.");
    ordensProducaoDisponiveis = await res.json();
  } catch (erro) {
    console.error(erro);
    ordensProducaoDisponiveis = [];
  }
}

async function carregarMaquinas(incluirInativas = false) {
  const container = document.getElementById("pills-maquinas");

  try {
    const res = await chamarApi(
      `/maquinas/?incluir_inativas=${incluirInativas}`,
    );

    if (!res.ok) throw new Error("Não foi possível carregar as máquinas.");

    maquinasDisponiveis = await res.json();

    if (maquinasDisponiveis.length === 0) {
      container.innerHTML = `<li class="nav-item"><span class="nav-link disabled">
        Nenhuma injetora cadastrada. Peça a um admin para cadastrar em "Máquinas".
      </span></li>`;
      return;
    }

    // Garante que sempre há um estado (mesmo vazio) para cada máquina.
    maquinasDisponiveis.forEach((m) => {
      if (!registrosState[m.numero_maquina]) {
        registrosState[m.numero_maquina] = {};
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
    const rotulo = m.descricao
      ? `Injetora ${m.numero_maquina}`
      : `Máquina ${m.numero_maquina}`;
    btn.textContent = m.ativo === false ? `${rotulo} (inativa)` : rotulo;
    btn.addEventListener("click", () => selecionarMaquina(m.numero_maquina));

    li.appendChild(btn);
    container.appendChild(li);
  });
}

function atualizarRelogio() {
  const agora = new Date();
  document.getElementById("relogio").innerText = agora.toLocaleTimeString(
    "pt-BR",
    { hour: "2-digit", minute: "2-digit" },
  );
}

function atualizarHorariosTurno() {
  renderizarTabela();
}

function selecionarMaquina(numeroMaquina) {
  maquinaAtiva = numeroMaquina;

  // Atualiza botões
  document.querySelectorAll(".btn-maq").forEach((btn) => {
    btn.classList.toggle("active", btn.dataset.numeroMaquina === numeroMaquina);
  });

  // Atualiza cabeçalho da máquina
  const info = maquinasDisponiveis.find(
    (m) => m.numero_maquina === numeroMaquina,
  );
  if (info) {
    document.getElementById("tituloMaquina").innerText =
      info.descricao || `Injetora ${info.numero_maquina}`;
    const badge = document.getElementById("badgeDetalheMaquina");
    if (info.cavidades && info.ciclo_padrao) {
      badge.innerText = `Cavidades: ${info.cavidades} | Ciclo: ${info.ciclo_padrao}s (padrão da máquina)`;
    } else {
      badge.innerText = "Sem cavidades/ciclo padrão cadastrados - defina pela peça";
    }
  }

  renderizarTabela();
}

function renderizarTabela() {
  const turno = document.getElementById("selectTurno").value;
  const horas = HORARIOS_POR_TURNO[turno] || [];
  const tbody = document.getElementById("corpoTabelaApontamento");
  tbody.innerHTML = "";

  if (!maquinaAtiva) return;

  const opcoesPecas = pecasDisponiveis
    .map(
      (p) =>
        `<option value="${p.id}">${escaparHtml(p.codigo)} - ${escaparHtml(p.descricao)}</option>`,
    )
    .join("");

  const opcoesOps = ordensProducaoDisponiveis
    .map(
      (o) =>
        `<option value="${o.id}">${escaparHtml(o.numero_op)}${o.produto_descricao ? " - " + escaparHtml(o.produto_descricao) : ""}</option>`,
    )
    .join("");

  horas.forEach((hora) => {
    const salvo = (registrosState[maquinaAtiva] || {})[hora] || {
      prod: "",
      inicio: "",
      retomada: "",
      motivo: "",
      produtoId: "",
      ordemProducaoId: "",
      paradaProgramada: false,
      cicloInformado: "",
      contadorParada: "",
      contadorRetomada: "",
    };

    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td class="fw-bold fs-5 text-secondary">${hora}</td>
      <td>
        <select class="form-select select-peca" onchange="onPecaSelecionada('${hora}', this.value)">
          <option value="" ${salvo.produtoId ? "" : "selected"}>— Selecionar —</option>
          ${opcoesPecas}
        </select>
      </td>
      <td>
        <select class="form-select select-op" onchange="salvarValor('${hora}', 'ordemProducaoId', this.value)">
          <option value="" ${salvo.ordemProducaoId ? "" : "selected"}>— Nenhuma —</option>
          ${opcoesOps}
        </select>
      </td>
      <td>
        <input type="number" min="0" class="form-control" placeholder="0" 
          value="${salvo.prod}" onchange="salvarValor('${hora}', 'prod', this.value)">
      </td>
      <td>
        <input type="number" min="0.1" step="0.1" class="form-control" placeholder="ciclo (s)"
          value="${salvo.cicloInformado}" onchange="salvarValor('${hora}', 'cicloInformado', this.value)">
      </td>
      <td>
        <input type="time" class="form-control mb-1" 
          value="${salvo.inicio}" onchange="salvarValor('${hora}', 'inicio', this.value)">
        <input type="number" min="0" class="form-control form-control-sm" placeholder="contador"
          value="${salvo.contadorParada}" onchange="salvarValor('${hora}', 'contadorParada', this.value)">
      </td>
      <td>
        <input type="time" class="form-control mb-1" 
          value="${salvo.retomada}" onchange="salvarValor('${hora}', 'retomada', this.value)">
        <input type="number" min="0" class="form-control form-control-sm" placeholder="contador"
          value="${salvo.contadorRetomada}" onchange="salvarValor('${hora}', 'contadorRetomada', this.value)">
      </td>
      <td>
        <input type="checkbox" class="form-check-input" title="Parada programada (não penaliza o OEE)"
          ${salvo.paradaProgramada ? "checked" : ""}
          onchange="salvarValor('${hora}', 'paradaProgramada', this.checked)">
      </td>
      <td>
        <input type="text" class="form-control text-start" placeholder="Ex: Molde travado" 
          value="${salvo.motivo}" onchange="salvarValor('${hora}', 'motivo', this.value)">
      </td>
    `;

    // Restaura os selects (o innerHTML acima recria os <select> do zero,
    // então marcar "selected" na string dificultaria escapar o id
    // corretamente - fazemos pela API do DOM em vez disso).
    if (salvo.produtoId) {
      tr.querySelector(".select-peca").value = String(salvo.produtoId);
    }
    if (salvo.ordemProducaoId) {
      tr.querySelector(".select-op").value = String(salvo.ordemProducaoId);
    }
    tbody.appendChild(tr);
  });
}

// Ao trocar a peça selecionada, pré-preenche o campo de ciclo com o
// ciclo médio cadastrado na peça (só quando o campo ainda estiver
// vazio, para não sobrescrever um valor que o operador já corrigiu
// manualmente) - deixa visível qual ciclo está sendo assumido, e
// ainda editável caso o molde esteja regulado diferente.
function onPecaSelecionada(hora, produtoId) {
  salvarValor(hora, "produtoId", produtoId);

  const registro = registrosState[maquinaAtiva][hora];
  if (!registro.cicloInformado && produtoId) {
    const peca = pecasDisponiveis.find((p) => String(p.id) === String(produtoId));
    if (peca && peca.ciclo_padrao) {
      registro.cicloInformado = peca.ciclo_padrao;
      renderizarTabela();
    }
  }
}

function salvarValor(hora, campo, valor) {
  if (!registrosState[maquinaAtiva]) {
    registrosState[maquinaAtiva] = {};
  }
  if (!registrosState[maquinaAtiva][hora]) {
    registrosState[maquinaAtiva][hora] = {
      prod: "",
      inicio: "",
      retomada: "",
      motivo: "",
      produtoId: "",
      ordemProducaoId: "",
      paradaProgramada: false,
      cicloInformado: "",
      contadorParada: "",
      contadorRetomada: "",
    };
  }

  // Parada programada só faz sentido com um horário de início registrado
  // (é o que o backend usa pra calcular quantos minutos excluir do OEE).
  if (campo === "paradaProgramada" && valor && !registrosState[maquinaAtiva][hora].inicio) {
    alert("Preencha o horário de início da parada antes de marcar como programada.");
    renderizarTabela();
    return;
  }

  registrosState[maquinaAtiva][hora][campo] = valor;
}

function escaparHtml(texto) {
  const div = document.createElement("div");
  div.textContent = texto;
  return div.innerHTML;
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
    registros: [],
  };

  // Formata os registros de todas as máquinas cadastradas (número dinâmico,
  // não mais fixo em 6).
  maquinasDisponiveis.forEach((m) => {
    const registrosMaquina = registrosState[m.numero_maquina] || {};
    for (const [hora, dados] of Object.entries(registrosMaquina)) {
      if (dados.prod !== "" || dados.inicio !== "") {
        payload.registros.push({
          numero_maquina: m.numero_maquina,
          hora_referencia: hora,
          prod_executada: parseInt(dados.prod || 0),
          produto_id: dados.produtoId ? parseInt(dados.produtoId) : null,
          ordem_producao_id: dados.ordemProducaoId ? parseInt(dados.ordemProducaoId) : null,
          ciclo_informado: dados.cicloInformado !== "" ? parseFloat(dados.cicloInformado) : null,
          inicio_parada: dados.inicio || null,
          retomada: dados.retomada || null,
          motivo_parada: dados.motivo || null,
          parada_programada: !!dados.paradaProgramada,
          contador_parada: dados.contadorParada !== "" ? parseInt(dados.contadorParada) : null,
          contador_retomada: dados.contadorRetomada !== "" ? parseInt(dados.contadorRetomada) : null,
        });
      }
    }
  });

  return { lider, payload };
}

// Envio para o Backend FastAPI (cria um turno novo, ou corrige um
// existente quando turnoEditandoId estiver definido).
async function confirmarFechamento() {
  const { lider, payload } = montarPayloadFechamento();
  if (!lider) {
    alert("Por favor, preencha o nome do líder antes de finalizar.");
    return;
  }

  const editando = !!turnoEditandoId;
  const caminho = editando
    ? `/turnos/${turnoEditandoId}`
    : `/turnos/fechamento`;
  const metodo = editando ? "PATCH" : "POST";

  try {
    const res = await chamarApi(caminho, {
      method: metodo,
      body: JSON.stringify(payload),
    });

    if (res.status === 403) {
      alert("Você não tem permissão para corrigir este turno.");
      return;
    }

    if (res.ok) {
      if (editando) {
        alert("✅ Turno corrigido com sucesso!");
        window.location.href = "historico.html";
      } else {
        alert(
          "✅ Fechamento de turno registrado e assinado com sucesso! O relatório será gerado.",
        );
        window.location.reload();
      }
    } else {
      const erro = await res.json().catch(() => null);
      alert(
        "⚠️ " +
          (erro?.detail ||
            "Erro ao registrar dados. Verifique a conexão com o servidor."),
      );
    }
  } catch (error) {
    // Sessão expirada: chamarApi já redirecionou para login.html, então
    // não mostramos um alerta de erro de conexão por cima do redirect.
    if (error.message === "Sessão expirada.") return;
    console.error("Erro na requisição:", error);
    alert("❌ Não foi possível conectar à API.");
  }
}
