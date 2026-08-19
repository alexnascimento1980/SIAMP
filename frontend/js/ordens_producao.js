let opsCarregadas = [];
let podeGerenciar = false;

document.addEventListener("DOMContentLoaded", async () => {
  const sessao = await exigirSessao();
  if (!sessao) return;

  podeGerenciar = sessao.perfil === "ADMIN" || sessao.perfil === "SUPERVISOR";
  if (!podeGerenciar) {
    document.querySelector(".card.shadow-sm.mb-3").style.display = "none";
  }

  document.getElementById("formNovaOp").addEventListener("submit", onSalvarOp);
  document
    .getElementById("formOpColapsavel")
    .addEventListener("show.bs.collapse", () => {
      document.getElementById("btnToggleForm").textContent = "Ocultar formulário";
    });
  document
    .getElementById("formOpColapsavel")
    .addEventListener("hide.bs.collapse", () => {
      document.getElementById("btnToggleForm").textContent = "Mostrar formulário";
    });

  carregarOps();
});

async function carregarOps() {
  const container = document.getElementById("listaOps");
  try {
    const res = await chamarApi("/ordens-producao/");
    if (!res.ok) throw new Error("Não foi possível carregar as ordens de produção.");
    opsCarregadas = await res.json();

    // Busca o comparativo (meta x real) de cada OP em paralelo.
    const comparativos = await Promise.all(
      opsCarregadas.map((op) =>
        chamarApi(`/ordens-producao/${op.id}/comparativo`)
          .then((r) => (r.ok ? r.json() : null))
          .catch(() => null),
      ),
    );

    renderizarLista(opsCarregadas, comparativos);
  } catch (erro) {
    console.error(erro);
    container.innerHTML = `<div class="text-center text-danger py-4">${erro.message}</div>`;
  }
}

function renderizarLista(ops, comparativos) {
  const container = document.getElementById("listaOps");
  container.innerHTML = "";

  if (ops.length === 0) {
    container.innerHTML = `<div class="text-center text-secondary py-4">Nenhuma Ordem de Produção cadastrada ainda.</div>`;
    return;
  }

  ops.forEach((op, i) => {
    const comp = comparativos[i];
    const item = document.createElement("div");
    item.className = "list-group-item p-3";

    const percentual = comp ? comp.percentual_atingido : null;
    const corBarra =
      percentual === null
        ? "bg-secondary"
        : percentual >= 100
          ? "bg-success"
          : percentual >= 60
            ? "bg-primary"
            : "bg-warning";

    const barraProgresso = comp
      ? `
        <div class="d-flex justify-content-between small text-secondary mb-1">
          <span>${comp.quantidade_produzida.toLocaleString("pt-BR")} / ${comp.quantidade_meta.toLocaleString("pt-BR")} pçs</span>
          <span>${comp.percentual_atingido}%</span>
        </div>
        <div class="progress" style="height: 8px;">
          <div class="progress-bar ${corBarra}" style="width: ${Math.min(percentual, 100)}%"></div>
        </div>
      `
      : `<div class="small text-secondary fst-italic">Sem máquina vinculada - comparativo indisponível.</div>`;

    const botoesGerenciar = podeGerenciar
      ? `
        <button class="btn btn-sm btn-outline-secondary" onclick="editarOp(${op.id})" title="Editar">
          <i class="bi bi-pencil-square"></i>
        </button>
        <button class="btn btn-sm btn-outline-danger" onclick="excluirOp(${op.id})" title="Remover">
          <i class="bi bi-trash"></i>
        </button>
      `
      : "";

    item.innerHTML = `
      <div class="d-flex justify-content-between align-items-start flex-wrap gap-2">
        <div>
          <div class="fw-bold">
            OP ${escaparHtml(op.numero_op)}
            ${op.lote ? `<span class="text-secondary fw-normal small">• Lote ${escaparHtml(op.lote)}</span>` : ""}
          </div>
          <div class="text-secondary small">
            ${escaparHtml(op.produto_descricao || "Produto não informado")}
            ${op.numero_maquina ? ` • Máquina ${escaparHtml(op.numero_maquina)}` : ""}
          </div>
          <div class="text-secondary small">
            Período: ${formatarData(op.periodo_inicio)} a ${formatarData(op.periodo_fim)}
          </div>
        </div>
        <div class="d-flex gap-1">${botoesGerenciar}</div>
      </div>
      <div class="mt-2" style="max-width: 400px;">${barraProgresso}</div>
    `;
    container.appendChild(item);
  });
}

function formatarData(isoDate) {
  if (!isoDate) return "-";
  const [ano, mes, dia] = isoDate.split("-");
  return `${dia}/${mes}/${ano}`;
}

function montarPayload() {
  const opcional = (id) => document.getElementById(id).value.trim() || null;
  const opcionalNumerico = (id) => {
    const v = document.getElementById(id).value;
    return v === "" ? null : parseFloat(v);
  };

  return {
    numero_op: document.getElementById("numeroOp").value.trim(),
    data_emissao: opcional("dataEmissao"),
    tipo_op: opcional("tipoOp"),
    setor_produtivo: opcional("setorProdutivo"),
    lote: opcional("lote"),
    periodo_inicio: document.getElementById("periodoInicio").value,
    periodo_fim: document.getElementById("periodoFim").value,
    produto_codigo: opcional("produtoCodigo"),
    produto_descricao: opcional("produtoDescricao"),
    quantidade_a_produzir: parseInt(document.getElementById("quantidadeAProduzir").value, 10),
    numero_maquina: opcional("numeroMaquina"),
    equipamento_descricao: opcional("equipamentoDescricao"),
    ferramenta_codigo: opcional("ferramentaCodigo"),
    ferramenta_descricao: opcional("ferramentaDescricao"),
    formula_codigo: opcional("formulaCodigo"),
    formula_descricao: opcional("formulaDescricao"),
    embalagem_codigo: opcional("embalagemCodigo"),
    embalagem_descricao: opcional("embalagemDescricao"),
    qtde_por_embalagem: opcionalNumerico("qtdePorEmbalagem"),
    qtde_embalagens_previstas: opcionalNumerico("qtdeEmbalagensPrevistas"),
    cavidades: opcionalNumerico("cavidades"),
    ciclo_segundos: opcionalNumerico("cicloSegundos"),
    qtde_produzida_por_hora_meta: opcionalNumerico("qtdeProduzidaPorHoraMeta"),
    peso_liquido_unitario: opcionalNumerico("pesoLiquidoUnitario"),
    peso_bruto_unitario: opcionalNumerico("pesoBrutoUnitario"),
    observacoes: opcional("observacoes"),
  };
}

async function onSalvarOp(evento) {
  evento.preventDefault();
  esconderMensagem();

  const opId = document.getElementById("opId").value;
  const payload = montarPayload();
  const editando = !!opId;

  const btn = document.getElementById("btnSalvarOp");
  btn.disabled = true;

  try {
    const caminho = editando ? `/ordens-producao/${opId}` : "/ordens-producao/";
    const metodo = editando ? "PATCH" : "POST";

    if (editando) {
      delete payload.numero_op; // código não é editável
    }

    const res = await chamarApi(caminho, {
      method: metodo,
      body: JSON.stringify(payload),
    });

    if (res.status === 409) {
      mostrarMensagem("Já existe uma Ordem de Produção com este número.", "danger");
      return;
    }

    if (!res.ok) {
      const erro = await res.json().catch(() => null);
      mostrarMensagem(
        erro?.detail || "Não foi possível salvar a Ordem de Produção.",
        "danger",
      );
      return;
    }

    cancelarEdicao();
    mostrarMensagem(
      editando ? "Ordem de Produção atualizada!" : "Ordem de Produção cadastrada!",
      "success",
    );
    carregarOps();
  } catch (erro) {
    mostrarMensagem(erro.message, "danger");
  } finally {
    btn.disabled = false;
  }
}

function editarOp(opId) {
  const op = opsCarregadas.find((o) => o.id === opId);
  if (!op) return;

  document.getElementById("opId").value = op.id;
  document.getElementById("numeroOp").value = op.numero_op;
  document.getElementById("numeroOp").disabled = true;
  document.getElementById("dataEmissao").value = op.data_emissao || "";
  document.getElementById("tipoOp").value = op.tipo_op || "";
  document.getElementById("setorProdutivo").value = op.setor_produtivo || "";
  document.getElementById("lote").value = op.lote || "";
  document.getElementById("periodoInicio").value = op.periodo_inicio;
  document.getElementById("periodoFim").value = op.periodo_fim;
  document.getElementById("produtoCodigo").value = op.produto_codigo || "";
  document.getElementById("produtoDescricao").value = op.produto_descricao || "";
  document.getElementById("quantidadeAProduzir").value = op.quantidade_a_produzir;
  document.getElementById("numeroMaquina").value = op.numero_maquina || "";
  document.getElementById("equipamentoDescricao").value = op.equipamento_descricao || "";
  document.getElementById("ferramentaCodigo").value = op.ferramenta_codigo || "";
  document.getElementById("ferramentaDescricao").value = op.ferramenta_descricao || "";
  document.getElementById("formulaCodigo").value = op.formula_codigo || "";
  document.getElementById("formulaDescricao").value = op.formula_descricao || "";
  document.getElementById("embalagemCodigo").value = op.embalagem_codigo || "";
  document.getElementById("embalagemDescricao").value = op.embalagem_descricao || "";
  document.getElementById("qtdePorEmbalagem").value = op.qtde_por_embalagem || "";
  document.getElementById("qtdeEmbalagensPrevistas").value = op.qtde_embalagens_previstas || "";
  document.getElementById("cavidades").value = op.cavidades || "";
  document.getElementById("cicloSegundos").value = op.ciclo_segundos || "";
  document.getElementById("qtdeProduzidaPorHoraMeta").value = op.qtde_produzida_por_hora_meta || "";
  document.getElementById("pesoLiquidoUnitario").value = op.peso_liquido_unitario || "";
  document.getElementById("pesoBrutoUnitario").value = op.peso_bruto_unitario || "";
  document.getElementById("observacoes").value = op.observacoes || "";

  document.getElementById("btnSalvarOp").innerHTML =
    '<i class="bi bi-check-circle me-1"></i>Salvar Alterações';
  document.getElementById("btnCancelarEdicao").style.display = "inline-block";

  new bootstrap.Collapse(document.getElementById("formOpColapsavel"), { show: true });
  document.getElementById("formOpColapsavel").scrollIntoView({ behavior: "smooth" });
}

function cancelarEdicao() {
  document.getElementById("formNovaOp").reset();
  document.getElementById("opId").value = "";
  document.getElementById("numeroOp").disabled = false;
  document.getElementById("btnSalvarOp").innerHTML =
    '<i class="bi bi-check-circle me-1"></i>Salvar Ordem de Produção';
  document.getElementById("btnCancelarEdicao").style.display = "none";
}

async function excluirOp(opId) {
  if (!confirm("Remover esta Ordem de Produção definitivamente?")) return;

  try {
    const res = await chamarApi(`/ordens-producao/${opId}`, { method: "DELETE" });
    if (!res.ok && res.status !== 204) {
      const erro = await res.json().catch(() => null);
      mostrarMensagem(erro?.detail || "Não foi possível remover.", "danger");
      return;
    }
    mostrarMensagem("Ordem de Produção removida.", "success");
    carregarOps();
  } catch (erro) {
    mostrarMensagem(erro.message, "danger");
  }
}

function mostrarMensagem(texto, tipo) {
  const el = document.getElementById("alertaMsg");
  el.textContent = texto;
  el.className = `alert alert-${tipo}`;
  el.classList.remove("d-none");
  el.scrollIntoView({ behavior: "smooth", block: "center" });
}

function esconderMensagem() {
  document.getElementById("alertaMsg").classList.add("d-none");
}

function escaparHtml(texto) {
  const div = document.createElement("div");
  div.textContent = texto;
  return div.innerHTML;
}
