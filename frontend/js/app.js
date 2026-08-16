// Base da API. Ajuste via variável global window.SIAMP_API_BASE_URL se
// o backend não estiver em localhost:8000 (ex. em produção).
const API_BASE_URL =
  window.SIAMP_API_BASE_URL || "http://localhost:8000/api/v1";

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

// Lista de máquinas ativas, carregada do backend (não é mais fixa em 6).
// Cada item: { id, numero_maquina, descricao, cavidades, ciclo_padrao }
let maquinasDisponiveis = [];
let maquinaAtiva = null; // guarda o numero_maquina (string) selecionado
// Estado centralizado dos apontamentos: dados[numero_maquina][hora] = { prod, inicio, retomada, motivo }
let registrosState = {};

// Inicialização
document.addEventListener("DOMContentLoaded", async () => {
  // Sem sessão válida, manda direto pra tela de login.
  const token = obterTokenSalvo();
  if (!token) {
    window.location.href = "login.html";
    return;
  }

  const perfil = obterPerfilDoToken(token);
  if (perfil === "ADMIN") {
    document.getElementById("linkUsuarios").classList.remove("d-none");
  }
  if (perfil === "ADMIN" || perfil === "SUPERVISOR") {
    document.getElementById("linkMaquinas").classList.remove("d-none");
  }

  document.getElementById("dataTurno").valueAsDate = new Date();
  atualizarRelogio();
  setInterval(atualizarRelogio, 1000);

  await carregarMaquinas();
  renderizarTabela();
});

async function carregarMaquinas() {
  const container = document.getElementById("pills-maquinas");

  try {
    const res = await fetch(`${API_BASE_URL}/maquinas/`, {
      headers: { Authorization: `Bearer ${obterTokenSalvo()}` },
    });

    if (res.status === 401) {
      localStorage.removeItem("siamp_token");
      window.location.href = "login.html";
      return;
    }

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
    btn.textContent = m.descricao
      ? `Injetora ${m.numero_maquina}`
      : `Máquina ${m.numero_maquina}`;
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
    document.getElementById("badgeDetalheMaquina").innerText =
      `Cavidades: ${info.cavidades} | Ciclo: ${info.ciclo_padrao}s`;
  }

  renderizarTabela();
}

function renderizarTabela() {
  const turno = document.getElementById("selectTurno").value;
  const horas = HORARIOS_POR_TURNO[turno] || [];
  const tbody = document.getElementById("corpoTabelaApontamento");
  tbody.innerHTML = "";

  if (!maquinaAtiva) return;

  horas.forEach((hora) => {
    const salvo = (registrosState[maquinaAtiva] || {})[hora] || {
      prod: "",
      inicio: "",
      retomada: "",
      motivo: "",
    };

    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td class="fw-bold fs-5 text-secondary">${hora}</td>
      <td>
        <input type="number" min="0" class="form-control" placeholder="0" 
          value="${salvo.prod}" onchange="salvarValor('${hora}', 'prod', this.value)">
      </td>
      <td>
        <input type="time" class="form-control" 
          value="${salvo.inicio}" onchange="salvarValor('${hora}', 'inicio', this.value)">
      </td>
      <td>
        <input type="time" class="form-control" 
          value="${salvo.retomada}" onchange="salvarValor('${hora}', 'retomada', this.value)">
      </td>
      <td>
        <input type="text" class="form-control text-start" placeholder="Ex: Molde travado" 
          value="${salvo.motivo}" onchange="salvarValor('${hora}', 'motivo', this.value)">
      </td>
    `;
    tbody.appendChild(tr);
  });
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
    };
  }
  registrosState[maquinaAtiva][hora][campo] = valor;
}

// Autenticação: sessão gerenciada pela tela de login (login.html/login.js).
// Aqui só lemos o token salvo e tratamos sessão expirada.
function obterTokenSalvo() {
  return localStorage.getItem("siamp_token");
}

function sair() {
  localStorage.removeItem("siamp_token");
  window.location.href = "login.html";
}

// Leitura client-side do payload do JWT, só para decidir o que mostrar na
// tela (ex.: exibir os links de Usuários/Máquinas para ADMIN/SUPERVISOR).
// O backend SEMPRE revalida a assinatura e a permissão de verdade em cada
// endpoint - isto aqui não é uma camada de segurança, é conveniência de UI.
function obterPerfilDoToken(token) {
  try {
    const payloadBase64 = token.split(".")[1];
    const payload = JSON.parse(
      atob(payloadBase64.replace(/-/g, "+").replace(/_/g, "/")),
    );
    return payload.perfil || null;
  } catch (erro) {
    return null;
  }
}

// Envio para o Backend FastAPI
async function confirmarFechamento() {
  const lider = document.getElementById("nomeLider").value.trim();
  if (!lider) {
    alert("Por favor, preencha o nome do líder antes de finalizar.");
    return;
  }

  const turnoSelect = document.getElementById("selectTurno");
  const payload = {
    nome_turno: turnoSelect.options[turnoSelect.selectedIndex].text,
    responsavel_nome: lider,
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
          inicio_parada: dados.inicio || null,
          retomada: dados.retomada || null,
          motivo_parada: dados.motivo || null,
        });
      }
    }
  });

  try {
    const res = await fetch(`${API_BASE_URL}/turnos/fechamento`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${obterTokenSalvo()}`,
      },
      body: JSON.stringify(payload),
    });

    if (res.status === 401) {
      localStorage.removeItem("siamp_token");
      alert("Sessão expirada. Faça login novamente.");
      window.location.href = "login.html";
      return;
    }

    if (res.ok) {
      alert(
        "✅ Fechamento de turno registrado e assinado com sucesso! O relatório será gerado.",
      );
      window.location.reload();
    } else {
      alert("⚠️ Erro ao registrar dados. Verifique a conexão com o servidor.");
    }
  } catch (error) {
    console.error("Erro na requisição:", error);
    alert("❌ Não foi possível conectar à API.");
  }
}
