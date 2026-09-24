document.addEventListener("DOMContentLoaded", async () => {
  const sessao = await exigirSessao();
  if (!sessao) return;

  const saudacao = document.getElementById("saudacao");
  if (sessao.nome) {
    saudacao.textContent = `Olá, ${sessao.nome}`;
    saudacao.classList.remove("d-none");
  }

  if (sessao.perfil === "ADMIN" || sessao.perfil === "SUPERVISOR") {
    document.getElementById("cardMaquinas").classList.remove("d-none");
  }
  if (sessao.perfil === "ADMIN") {
    document.getElementById("cardPecas").classList.remove("d-none");
    document.getElementById("cardOrdensProducao").classList.remove("d-none");
    document.getElementById("cardUsuarios").classList.remove("d-none");
    document.getElementById("cardDestinatarios").classList.remove("d-none");
  }
});
