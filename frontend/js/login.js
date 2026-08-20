document.addEventListener("DOMContentLoaded", async () => {
  // Se já existe uma sessão válida, não faz sentido mostrar o login de novo.
  try {
    const res = await fetch(`${API_BASE_URL}/auth/me`, {
      credentials: "include",
    });
    if (res.ok) {
      window.location.href = "home.html";
      return;
    }
  } catch (erro) {
    // Sem conexão com a API ainda: deixa continuar na tela de login.
  }

  document.getElementById("formLogin").addEventListener("submit", onSubmit);
});

async function onSubmit(evento) {
  evento.preventDefault();

  const email = document.getElementById("email").value.trim();
  const senha = document.getElementById("senha").value;
  esconderErro();

  if (!email || !senha) {
    mostrarErro("Preencha e-mail e senha.");
    return;
  }

  definirCarregando(true);

  const corpo = new URLSearchParams();
  corpo.set("username", email);
  corpo.set("password", senha);

  try {
    const res = await fetch(`${API_BASE_URL}/auth/login`, {
      method: "POST",
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
      // O backend define o cookie httpOnly de sessão na resposta; o
      // navegador só o guarda se a request for feita com credentials
      // "include".
      credentials: "include",
      body: corpo,
    });

    if (res.status === 401 || res.status === 403) {
      mostrarErro("E-mail ou senha inválidos.");
      return;
    }

    if (res.status === 429) {
      mostrarErro("Muitas tentativas. Aguarde um minuto e tente novamente.");
      return;
    }

    if (!res.ok) {
      mostrarErro("Não foi possível entrar. Tente novamente em instantes.");
      return;
    }

    window.location.href = "home.html";
  } catch (error) {
    console.error("Erro no login:", error);
    mostrarErro(
      "Não foi possível conectar ao servidor. Verifique sua conexão.",
    );
  } finally {
    definirCarregando(false);
  }
}

function mostrarErro(mensagem) {
  const alerta = document.getElementById("alertaErro");
  alerta.textContent = mensagem;
  alerta.classList.remove("d-none");
}

function esconderErro() {
  document.getElementById("alertaErro").classList.add("d-none");
}

function definirCarregando(carregando) {
  document.getElementById("btnEntrar").disabled = carregando;
  document.getElementById("btnEntrarTexto").textContent = carregando
    ? "Entrando..."
    : "Entrar";
  document
    .getElementById("btnEntrarSpinner")
    .classList.toggle("d-none", !carregando);
}
