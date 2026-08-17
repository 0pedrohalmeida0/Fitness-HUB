/* ============================================================
   Fitness Hub — API client
   Autenticação via cookies httpOnly (defesa contra XSS).

   O back seta `fh_access_token` (path /) e `fh_refresh_token`
   (path /auth) no login/refresh. Como são httpOnly, o JS não
   consegue ler — mas o browser envia automaticamente em requests
   pro mesmo origin.
   ============================================================ */

const API_BASE_URL = 'http://localhost:8000';

/**
 * Wrapper sobre fetch que:
 * - Envia cookies automaticamente (credentials: 'include')
 * - Trata 401 fazendo refresh automático (se possível)
 * - Converte erros em exceptions com mensagem útil
 */
async function apiFetch(path, options = {}) {
  const url = `${API_BASE_URL}${path}`;

  const config = {
    credentials: 'include',  // ENVIA cookies httpOnly automaticamente
    headers: {
      'Content-Type': 'application/json',
      ...(options.headers || {}),
    },
    ...options,
  };

  // Se body é objeto, serializa
  if (config.body && typeof config.body === 'object' && !(config.body instanceof FormData)) {
    config.body = JSON.stringify(config.body);
  }

  let response = await fetch(url, config);

  // Token expirou — tenta refresh (apenas uma vez, mesmo com chamadas paralelas)
  if (response.status === 401 && !path.startsWith('/auth/')) {
    const refreshed = await ensureFreshToken();
    if (refreshed) {
      // Refaz a requisição (cookies novos vão junto automaticamente)
      response = await fetch(url, config);
    } else {
      // Refresh falhou — manda pro login
      window.location.href = 'login.html';
      return;
    }
  }

  if (!response.ok) {
    let message = `Erro ${response.status}`;
    try {
      const data = await response.json();
      if (data.detail) {
        message = Array.isArray(data.detail)
          ? data.detail.map((d) => d.msg).join(', ')
          : data.detail;
      }
    } catch (e) { /* ignore */ }
    const err = new Error(message);
    err.status = response.status;
    throw err;
  }

  // 204 No Content
  if (response.status === 204) return null;

  return response.json();
}

// Variável de controle: se já tem refresh em andamento, outras chamadas aguardam
let _refreshInFlight = null;

async function ensureFreshToken() {
  if (_refreshInFlight) return _refreshInFlight;
  _refreshInFlight = tryRefreshToken();
  try {
    return await _refreshInFlight;
  } finally {
    _refreshInFlight = null;
  }
}

async function tryRefreshToken() {
  try {
    // O cookie fh_refresh_token é enviado automaticamente
    const response = await fetch(`${API_BASE_URL}/auth/refresh`, {
      method: 'POST',
      credentials: 'include',
      headers: { 'Content-Type': 'application/json' },
      // Envia body vazio — o refresh_token vem do cookie
      body: JSON.stringify({}),
    });
    return response.ok;
  } catch (e) {
    return false;
  }
}

// Helpers de conveniência
const api = {
  get: (path) => apiFetch(path),
  post: (path, body) => apiFetch(path, { method: 'POST', body }),
  patch: (path, body) => apiFetch(path, { method: 'PATCH', body }),
  del: (path) => apiFetch(path, { method: 'DELETE' }),
};

// ============================================================
// Endpoints específicos do módulo Dieta
// ============================================================
const alimentosApi = {
  list: (search, page = 1) => {
    const params = new URLSearchParams();
    if (search) params.set('search', search);
    params.set('page', page);
    return api.get(`/alimentos?${params}`);
  },
  get: (id) => api.get(`/alimentos/${id}`),
  create: (data) => api.post('/alimentos', data),
};

const alimentacaoApi = {
  list: (date) => api.get(`/alimentacao?data=${date}`),
  resumo: (date) => api.get(`/alimentacao/resumo?data=${date}`),
  create: (data) => api.post('/alimentacao', data),
  delete: (id) => api.del(`/alimentacao/${id}`),
};

// ============================================================
// Auth
// ============================================================
const authApi = {
  me: () => api.get('/auth/me'),
  logout: async () => {
    // Chama logout no back (revoga refresh + limpa cookies).
    // O body é vazio — o refresh_token vem do cookie.
    try { await api.post('/auth/logout', {}); } catch (e) { /* ignore */ }
    // Limpa qualquer storage legado (caso o user tenha tokens antigos)
    localStorage.removeItem('fh_access_token');
    localStorage.removeItem('fh_refresh_token');
    localStorage.removeItem('fh_token_type');
    window.location.href = 'login.html';
  },
};
