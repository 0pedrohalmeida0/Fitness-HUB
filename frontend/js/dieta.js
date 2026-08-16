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
  return new Date().toISOString().split('T')[0];
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

  try {
    const registros = await alimentacaoApi.list(data);
    if (registros.length === 0) {
      lista.innerHTML = '<p class="empty-state">Nenhum registro nesse dia. Adicione seu primeiro consumo!</p>';
      return;
    }
    // Agrupa por refeição
    const grupos = {};
    REFEICAO_ORDER.forEach(r => grupos[r] = []);
    registros.forEach(r => {
      if (grupos[r.refeicao]) grupos[r.refeicao].push(r);
    });

    lista.innerHTML = REFEICAO_ORDER
      .filter(r => grupos[r].length > 0)
      .map(r => `
        <div class="registro-group">
          <div class="registro-group-title">${REFEICAO_LABEL[r]}</div>
          ${grupos[r].map(reg => {
            const fator = reg.quantidade / reg.alimento_porcao_base_g;
            const kcal = reg.alimento_calorias * fator;
            return `
              <div class="registro">
                <div class="registro-refeicao">${REFEICAO_LABEL[r].substring(0,3).toUpperCase()}</div>
                <div class="registro-info">
                  <h3>${reg.alimento_nome}</h3>
                  <p><b>${reg.quantidade}g</b> · ${Math.round(kcal)} kcal · ${(reg.alimento_protein * fator).toFixed(1)}g proteína</p>
                </div>
                <button class="registro-delete" data-delete-id="${reg.id}" aria-label="Remover">
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                    <polyline points="3,6 5,6 21,6"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/>
                  </svg>
                </button>
              </div>
            `;
          }).join('')}
        </div>
      `).join('');

    // Adiciona listeners nos botões de delete
    lista.querySelectorAll('[data-delete-id]').forEach(btn => {
      btn.addEventListener('click', async (e) => {
        const id = e.currentTarget.getAttribute('data-delete-id');
        if (!confirm('Remover esse registro?')) return;
        try {
          await alimentacaoApi.delete(id);
          await carregarDiario(data);
          await carregarResumo(data);
        } catch (err) {
          alert('Erro: ' + err.message);
        }
      });
    });
  } catch (e) {
    lista.innerHTML = `<p class="empty-state">Erro ao carregar: ${e.message}</p>`;
  }
}

// ============================================================
// Catálogo
// ============================================================
let catalogoSearchTimeout;

async function carregarCatalogo(search = '') {
  const lista = document.getElementById('catalogo-lista');
  try {
    const data = await alimentosApi.list(search);
    if (data.items.length === 0) {
      lista.innerHTML = '<p class="empty-state">Nenhum alimento encontrado.</p>';
      return;
    }
    lista.innerHTML = data.items.map(al => `
      <div class="alimento-card">
        <h3>${al.nome}</h3>
        <div class="alimento-macros">
          <span><b>${al.calorias}</b> kcal</span>
          <span><b>${al.protein}g</b> P</span>
          <span><b>${al.carbo}g</b> C</span>
          <span><b>${al.fibras}g</b> F</span>
        </div>
        <p style="font-size:11px;color:#A1A1AA;margin-top:6px;">por ${al.porcao_base_g}g</p>
      </div>
    `).join('');
  } catch (e) {
    lista.innerHTML = `<p class="empty-state">Erro: ${e.message}</p>`;
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
  if (term.length < 2) {
    sugestoesEl.hidden = true;
    return;
  }
  try {
    const data = await alimentosApi.list(term);
    if (data.items.length === 0) {
      sugestoesEl.innerHTML = '<div class="sugestao-item">Nenhum resultado</div>';
      sugestoesEl.hidden = false;
      return;
    }
    sugestoesEl.innerHTML = data.items.slice(0, 8).map(al => `
      <div class="sugestao-item" data-id="${al.id}" data-nome="${al.nome}">
        <strong>${al.nome}</strong> · <span style="color:#71717A;">${al.calorias} kcal / ${al.porcao_base_g}g</span>
      </div>
    `).join('');
    sugestoesEl.hidden = false;

    // Listener nos itens
    sugestoesEl.querySelectorAll('.sugestao-item').forEach(item => {
      item.addEventListener('click', () => {
        const id = item.getAttribute('data-id');
        const nome = item.getAttribute('data-nome');
        document.getElementById('consumo-alimento-id').value = id;
        document.getElementById('consumo-alimento-nome').textContent = `✓ ${nome}`;
        document.getElementById('consumo-alimento-nome').hidden = false;
        document.getElementById('consumo-busca').value = nome;
        sugestoesEl.hidden = true;
      });
    });
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
        alimento_id: parseInt(alimentoId),
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
