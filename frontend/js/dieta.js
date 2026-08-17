/* ============================================================
   Fitness Hub — Dieta page
   Lógica de UI: tabs, diário, catálogo, adicionar consumo/alimento
   ============================================================ */

const REFEICAO_LABEL = {
  cafe_manha: 'Café da manhã',
  lanche_manha: 'Lanche da manhã',
  almoco: 'Almoço',
  lanche_tarde: 'Lanche da tarde',
  jantar: 'Jantar',
  ceia: 'Ceia',
};

const REFEICAO_ORDER = ['cafe_manha', 'lanche_manha', 'almoco', 'lanche_tarde', 'jantar', 'ceia'];

// ============================================================
// Helpers
// ============================================================
function todayISO() {
  /**
   * Data de hoje no formato YYYY-MM-DD, em timezone LOCAL (não UTC).
   * `toISOString()` retorna UTC — em Brasil (UTC-3) à meia-noite
   * mostraria o dia anterior. Usamos componentes locais.
   */
  const d = new Date();
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, '0');
  const day = String(d.getDate()).padStart(2, '0');
  return `${y}-${m}-${day}`;
}

function formatDate(iso) {
  const [y, m, d] = iso.split('-');
  return `${d}/${m}/${y}`;
}

function showError(target, msg) {
  const el = document.getElementById(target);
  if (!el) return;
  el.textContent = msg;
  el.hidden = false;
  setTimeout(() => { el.hidden = true; }, 6000);
}

function setButtonLoading(btn, isLoading) {
  if (isLoading) {
    btn.classList.add('is-loading');
    btn.disabled = true;
  } else {
    btn.classList.remove('is-loading');
    btn.disabled = false;
  }
}

// ============================================================
// Helpers de DOM seguro (anti-XSS)
//
// IMPORTANTE: este helper NÃO tem opção `html` (innerHTML). Use
// sempre `text` para texto (escapa automaticamente) ou children
// com elementos DOM. Se precisar mesmo de HTML cru (raro),
// use `elUnsafe()` abaixo com consciência do risco de XSS.
// ============================================================
function el(tag, attrs = {}, children = []) {
  const node = document.createElement(tag);
  for (const [key, value] of Object.entries(attrs)) {
    if (value == null) continue;  // ignora null/undefined
    if (key === 'class') node.className = value;
    else if (key === 'text') node.textContent = value;  // seguro
    else if (key === 'html') {
      // Não permitido — log pra debug
      console.warn(
        '[el] opção `html` removida por segurança. Use `text` ou children.'
      );
    } else if (key.startsWith('on') && typeof value === 'function') {
      node.addEventListener(key.slice(2).toLowerCase(), value);
    } else if (key.startsWith('data-') || key === 'style' || key === 'href' || key === 'src') {
      node.setAttribute(key, value);
    } else {
      node.setAttribute(key, value);
    }
  }
  for (const child of children) {
    if (child == null) continue;
    if (typeof child === 'string') node.appendChild(document.createTextNode(child));
    else node.appendChild(child);
  }
  return node;
}

/**
 * Helper para inserir HTML cru. EVITE usar com dados de usuário.
 * Use apenas com strings hardcoded (ex: ícones SVG estáticos).
 *
 * @param {string} htmlString HTML seguro (não-sanitizado)
 * @returns {DocumentFragment}
 */
function elUnsafe(htmlString) {
  const tpl = document.createElement('template');
  tpl.innerHTML = htmlString;
  return tpl.content.cloneNode(true);
}

// ============================================================
// Auth check
// ============================================================
async function checkAuth() {
  const token = localStorage.getItem('fh_access_token');
  if (!token) {
    window.location.href = 'login.html';
    return null;
  }
  try {
    const me = await authApi.me();
    return me;
  } catch (e) {
    window.location.href = 'login.html';
    return null;
  }
}

// ============================================================
// Resumo
// ============================================================
async function carregarResumo(data) {
  try {
    const resumo = await alimentacaoApi.resumo(data);
    document.getElementById('stat-kcal').textContent = Math.round(resumo.total_calorias);
    document.getElementById('stat-protein').textContent = resumo.total_protein.toFixed(1);
    document.getElementById('stat-carbo').textContent = resumo.total_carbo.toFixed(1);
    document.getElementById('stat-fibras').textContent = resumo.total_fibras.toFixed(1);
    document.getElementById('stat-gramas').textContent = Math.round(resumo.total_gramas);
  } catch (e) {
    console.error('Erro ao carregar resumo:', e);
  }
}

// ============================================================
// Diário
// ============================================================
async function carregarDiario(data) {
  const lista = document.getElementById('diario-lista');
  const titulo = document.getElementById('diario-titulo');
  titulo.textContent = `Registros de ${formatDate(data)}`;

  // Limpa
  lista.replaceChildren();

  try {
    const registros = await alimentacaoApi.list(data);
    if (registros.length === 0) {
      lista.appendChild(el('p', { class: 'empty-state', text: 'Nenhum registro nesse dia. Adicione seu primeiro consumo!' }));
      return;
    }

    // Agrupa por refeição
    const grupos = {};
    REFEICAO_ORDER.forEach(r => grupos[r] = []);
    registros.forEach(r => {
      if (grupos[r.refeicao]) grupos[r.refeicao].push(r);
    });

    REFEICAO_ORDER.filter(r => grupos[r].length > 0).forEach(r => {
      const groupEl = el('div', { class: 'registro-group' });
      groupEl.appendChild(el('div', { class: 'registro-group-title', text: REFEICAO_LABEL[r] }));

      grupos[r].forEach(reg => {
        const fator = reg.alimento_porcao_base_g > 0 ? reg.quantidade / reg.alimento_porcao_base_g : 0;
        const kcal = reg.alimento_calorias * fator;

        const registroEl = el('div', { class: 'registro' });
        registroEl.appendChild(el('div', {
          class: 'registro-refeicao',
          text: REFEICAO_LABEL[r].substring(0, 3).toUpperCase(),
        }));

        const infoEl = el('div', { class: 'registro-info' });
        infoEl.appendChild(el('h3', { text: reg.alimento_nome }));
        const pEl = el('p');
        pEl.appendChild(el('b', { text: `${reg.quantidade}g` }));
        pEl.appendChild(document.createTextNode(` · ${Math.round(kcal)} kcal · `));
        pEl.appendChild(el('b', { text: `${(reg.alimento_protein * fator).toFixed(1)}g` }));
        pEl.appendChild(document.createTextNode(' proteína'));
        infoEl.appendChild(pEl);
        registroEl.appendChild(infoEl);

        const deleteBtn = el('button', {
          class: 'registro-delete',
          'data-delete-id': reg.id,
          'aria-label': 'Remover',
        });
        deleteBtn.innerHTML = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="3,6 5,6 21,6"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/></svg>`;
        deleteBtn.addEventListener('click', async () => {
          if (!confirm('Remover esse registro?')) return;
          try {
            await alimentacaoApi.delete(reg.id);
            await carregarDiario(data);
            await carregarResumo(data);
          } catch (err) {
            alert('Erro: ' + err.message);
          }
        });
        registroEl.appendChild(deleteBtn);
        groupEl.appendChild(registroEl);
      });

      lista.appendChild(groupEl);
    });
  } catch (e) {
    lista.appendChild(el('p', { class: 'empty-state', text: `Erro ao carregar: ${e.message}` }));
  }
}

// ============================================================
// Catálogo
// ============================================================
let catalogoSearchTimeout;

async function carregarCatalogo(search = '') {
  const lista = document.getElementById('catalogo-lista');
  lista.replaceChildren();
  try {
    const data = await alimentosApi.list(search);
    if (data.items.length === 0) {
      lista.appendChild(el('p', { class: 'empty-state', text: 'Nenhum alimento encontrado.' }));
      return;
    }
    data.items.forEach(al => {
      const cardEl = el('div', { class: 'alimento-card' });
      cardEl.appendChild(el('h3', { text: al.nome }));

      const macrosEl = el('div', { class: 'alimento-macros' });
      [
        `${al.calorias} kcal`,
        `${al.protein}g P`,
        `${al.carbo}g C`,
        `${al.fibras}g F`,
      ].forEach(text => {
        const span = el('span');
        const parts = text.split(' ');
        span.appendChild(el('b', { text: parts[0] }));
        span.appendChild(document.createTextNode(' ' + parts[1]));
        macrosEl.appendChild(span);
      });
      cardEl.appendChild(macrosEl);

      const porcaoEl = el('p', { style: 'font-size:11px;color:#A1A1AA;margin-top:6px;' });
      porcaoEl.appendChild(document.createTextNode(`por ${al.porcao_base_g}g`));
      cardEl.appendChild(porcaoEl);

      lista.appendChild(cardEl);
    });
  } catch (e) {
    lista.appendChild(el('p', { class: 'empty-state', text: `Erro: ${e.message}` }));
  }
}

// ============================================================
// Modal: Adicionar consumo
// ============================================================
function abrirModalConsumo() {
  document.getElementById('modal-consumo').hidden = false;
  document.getElementById('consumo-busca').value = '';
  document.getElementById('consumo-alimento-id').value = '';
  document.getElementById('consumo-alimento-nome').hidden = true;
  document.getElementById('consumo-sugestoes').hidden = true;
  document.getElementById('consumo-quantidade').value = 100;
  document.getElementById('consumo-refeicao').value = 'almoco';
  document.getElementById('consumo-busca').focus();
}

function fecharModal() {
  document.getElementById('modal-consumo').hidden = true;
}

let consumoSearchTimeout;
async function buscarAlimentosParaConsumo(term) {
  const sugestoesEl = document.getElementById('consumo-sugestoes');
  sugestoesEl.replaceChildren();
  if (term.length < 2) {
    sugestoesEl.hidden = true;
    return;
  }
  try {
    const data = await alimentosApi.list(term);
    if (data.items.length === 0) {
      const itemEl = el('div', { class: 'sugestao-item', text: 'Nenhum resultado' });
      sugestoesEl.appendChild(itemEl);
      sugestoesEl.hidden = false;
      return;
    }
    data.items.slice(0, 8).forEach(al => {
      const itemEl = el('div', {
        class: 'sugestao-item',
        'data-id': al.id,
        'data-nome': al.nome,
      });
      itemEl.appendChild(el('strong', { text: al.nome }));
      itemEl.appendChild(document.createTextNode(` · ${al.calorias} kcal / ${al.porcao_base_g}g`));

      itemEl.addEventListener('click', () => {
        const id = itemEl.getAttribute('data-id');
        const nome = itemEl.getAttribute('data-nome');
        document.getElementById('consumo-alimento-id').value = id;
        document.getElementById('consumo-alimento-nome').textContent = `✓ ${nome}`;
        document.getElementById('consumo-alimento-nome').hidden = false;
        document.getElementById('consumo-busca').value = nome;
        sugestoesEl.hidden = true;
      });
      sugestoesEl.appendChild(itemEl);
    });
    sugestoesEl.hidden = false;
  } catch (e) {
    console.error(e);
  }
}

// ============================================================
// Init
// ============================================================
let dataAtual = todayISO();

document.addEventListener('DOMContentLoaded', async () => {
  // Auth
  const me = await checkAuth();
  if (!me) return;
  document.getElementById('user-name').textContent = `@${me.username}`;
  document.getElementById('logout-link').addEventListener('click', (e) => {
    e.preventDefault();
    authApi.logout();
  });

  // Data picker
  const dataInput = document.getElementById('data-selecionada');
  dataInput.value = dataAtual;
  dataInput.addEventListener('change', async () => {
    dataAtual = dataInput.value;
    await carregarResumo(dataAtual);
    await carregarDiario(dataAtual);
  });

  // Tabs
  document.querySelectorAll('.tab').forEach(tab => {
    tab.addEventListener('click', () => {
      document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
      document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
      tab.classList.add('active');
      const target = tab.getAttribute('data-tab');
      document.getElementById(`tab-${target}`).classList.add('active');

      // Carrega dados quando troca de tab
      if (target === 'catalogo') carregarCatalogo();
    });
  });

  // Modal
  document.getElementById('btn-abrir-add-consumo').addEventListener('click', abrirModalConsumo);
  document.querySelectorAll('[data-close-modal]').forEach(el => {
    el.addEventListener('click', fecharModal);
  });
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') fecharModal();
  });

  // Busca no modal
  document.getElementById('consumo-busca').addEventListener('input', (e) => {
    clearTimeout(consumoSearchTimeout);
    consumoSearchTimeout = setTimeout(() => buscarAlimentosParaConsumo(e.target.value), 300);
  });

  // Submit consumo
  document.getElementById('form-consumo').addEventListener('submit', async (e) => {
    e.preventDefault();
    const btn = e.currentTarget.querySelector('button[type=submit]');
    const alimentoId = document.getElementById('consumo-alimento-id').value;
    if (!alimentoId) {
      showError('consumo-error', 'Selecione um alimento da lista.');
      return;
    }
    setButtonLoading(btn, true);
    try {
      await alimentacaoApi.create({
        alimento_id: parseInt(alimentoId, 10),
        quantidade: parseFloat(document.getElementById('consumo-quantidade').value),
        refeicao: document.getElementById('consumo-refeicao').value,
        data: dataAtual,
      });
      fecharModal();
      await carregarResumo(dataAtual);
      await carregarDiario(dataAtual);
    } catch (err) {
      showError('consumo-error', err.message);
      setButtonLoading(btn, false);
    }
  });

  // Submit adicionar alimento
  document.getElementById('form-add-alimento').addEventListener('submit', async (e) => {
    e.preventDefault();
    const btn = e.currentTarget.querySelector('button[type=submit]');
    setButtonLoading(btn, true);

    const payload = {
      nome: document.getElementById('alimento-nome').value.trim(),
      calorias: parseFloat(document.getElementById('alimento-calorias').value) || 0,
      porcao_base_g: parseFloat(document.getElementById('alimento-porcao').value) || 100,
      protein: parseFloat(document.getElementById('alimento-proteina').value) || 0,
      carbo: parseFloat(document.getElementById('alimento-carbo').value) || 0,
      acucares: parseFloat(document.getElementById('alimento-acucares').value) || 0,
      fibras: parseFloat(document.getElementById('alimento-fibras').value) || 0,
      sodio: parseFloat(document.getElementById('alimento-sodio').value) || 0,
    };

    try {
      const result = await alimentosApi.create(payload);
      const msg = result.status === 'pending'
        ? 'Alimento enviado para análise! Admin vai revisar.'
        : 'Alimento criado e aprovado!';
      alert(msg);
      e.target.reset();
      // Volta pra tab do diário
      document.querySelector('.tab[data-tab=diario]').click();
    } catch (err) {
      showError('add-error', err.message);
    } finally {
      setButtonLoading(btn, false);
    }
  });

  // Busca no catálogo (com debounce)
  document.getElementById('catalogo-search').addEventListener('input', (e) => {
    clearTimeout(catalogoSearchTimeout);
    catalogoSearchTimeout = setTimeout(() => carregarCatalogo(e.target.value), 300);
  });

  // Carrega inicial
  await carregarResumo(dataAtual);
  await carregarDiario(dataAtual);
});
