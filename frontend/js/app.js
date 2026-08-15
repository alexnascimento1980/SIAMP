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
  ], //[cite: 1]
  2: ["14:00", "15:00", "16:00", "17:00", "18:00", "19:00", "20:00", "21:00"], //[cite: 1]
  3: ["22:00", "23:00", "00:00", "01:00", "02:00", "03:00", "04:00"], //[cite: 1]
};

// Dados padrão das injetoras 1 a 6
const MAQUINAS_INFO = {
  1: { nome: "Injetora 1", cavidades: 4, ciclo: 18.5 },
  2: { nome: "Injetora 2", cavidades: 2, ciclo: 22.0 },
  3: { nome: "Injetora 3", cavidades: 8, ciclo: 15.0 },
  4: { nome: "Injetora 4", cavidades: 4, ciclo: 20.0 },
  5: { nome: "Injetora 5", cavidades: 1, ciclo: 30.0 },
  6: { nome: "Injetora 6", cavidades: 6, ciclo: 16.5 },
};

let maquinaAtiva = 1;
// Estado centralizado dos apontamentos: dados[maquinaId][hora] = { prod, inicio_parada, retomada, motivo }
let registrosState = {};

// Inicialização
document.addEventListener("DOMContentLoaded", () => {
  document.getElementById("dataTurno").valueAsDate = new Date();
  atualizarRelogio();
  setInterval(atualizarRelogio, 1000);
  inicializarEstado();
  renderizarTabela();
});

function atualizarRelogio() {
  const agora = new Date();
  document.getElementById("relogio").innerText = agora.toLocaleTimeString(
    "pt-BR",
    { hour: "2-digit", minute: "2-digit" },
  );
}

function inicializarEstado() {
  for (let m = 1; m <= 6; m++) {
    registrosState[m] = {};
  }
}

function atualizarHorariosTurno() {
  renderizarTabela();
}

function selecionarMaquina(numMaquina) {
  maquinaAtiva = numMaquina;

  // Atualiza botões
  document.querySelectorAll(".btn-maq").forEach((btn, idx) => {
    btn.classList.toggle("active", idx + 1 === numMaquina);
  });

  // Atualiza cabeçalho da máquina
  const info = MAQUINAS_INFO[numMaquina];
  document.getElementById("tituloMaquina").innerText = info.nome;
  document.getElementById("badgeDetalheMaquina").innerText =
    `Cavidades: ${info.cavidades} | Ciclo: ${info.ciclo}s`;

  renderizarTabela();
}

function renderizarTabela() {
  const turno = document.getElementById("selectTurno").value;
  const horas = HORARIOS_POR_TURNO[turno] || [];
  const tbody = document.getElementById("corpoTabelaApontamento");
  tbody.innerHTML = "";

  horas.forEach((hora) => {
    const salvo = registrosState[maquinaAtiva][hora] || {
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

// Autenticação: o backend agora exige um Bearer token em todas as
// rotas de dados. Fluxo simples via prompt() — para produção, trocar
// por uma tela de login de verdade.
function obterTokenSalvo() {
  return localStorage.getItem("siamp_token");
}

async function garantirLogin() {
  if (obterTokenSalvo()) return true;

  const email = prompt("E-mail:");
  const senha = email ? prompt("Senha:") : null;
  if (!email || !senha) return false;

  const corpo = new URLSearchParams();
  corpo.set("username", email);
  corpo.set("password", senha);

  try {
    const res = await fetch(`${API_BASE_URL}/auth/login`, {
      method: "POST",
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
      body: corpo,
    });
    if (!res.ok) {
      alert("Login inválido.");
      return false;
    }
    const data = await res.json();
    localStorage.setItem("siamp_token", data.access_token);
    return true;
  } catch (error) {
    console.error("Erro no login:", error);
    alert("Não foi possível autenticar.");
    return false;
  }
}

// Envio para o Backend FastAPI
async function confirmarFechamento() {
  const autenticado = await garantirLogin();
  if (!autenticado) return;

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

  // Formata os registros de todas as 6 máquinas
  for (let m = 1; m <= 6; m++) {
    for (const [hora, dados] of Object.entries(registrosState[m])) {
      if (dados.prod !== "" || dados.inicio !== "") {
        payload.registros.push({
          numero_maquina: String(m),
          hora_referencia: hora,
          prod_executada: parseInt(dados.prod || 0),
          inicio_parada: dados.inicio || null,
          retomada: dados.retomada || null,
          motivo_parada: dados.motivo || null,
        });
      }
    }
  }

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
      alert("Sessão expirada. Faça login novamente e tente de novo.");
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
