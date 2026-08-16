/* ============================================================
   Fitness Hub — API client
   Helper genérico pra chamadas autenticadas à API
   ============================================================ */

const API_BASE_URL = 'http://localhost:8000';

/**
 * Wrapper sobre fetch que:
 * - Adiciona o token JWT automaticamente
 * - Trata 401 fazendo refresh automático (se possível)
 * - Converte erros em exceptions com mensagem útil
 */
async function apiFetch(path, options = {}) {
  const url = `${API_BASE_URL}${path}`;
  const token = localStorage.getItem('fh_access_token');

  const config = {
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { 'Authorization': `Bearer ${token}` } : {}),
      ...(options.headers || {}),
    },
    ...options,
  };

  // Se body é objeto, serializa
  if (config.body && typeof config.body === 'object' && !(config.body instanceof FormData)) {
    config.body = JSON.stringify(config.body);
  }

  let response = await fetch(url, config);

  // Token expirou — tenta refresh
  if (response.status === 401 && !path.startsWith('/auth/')) {
    const refreshed = await tryRefreshToken();
    if (refreshed) {
      // Refaz a requisição com o token novo
      config.headers['Authorization'] = `Bearer ${localStorage.getItem('fh_access_token')}`;
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

async function tryRefreshToken() {
  const refresh = localStorage.getItem('fh_refresh_token');
  if (!refresh) return false;

  try {
    const response = await fetch(`${API_BASE_URL}/auth/refresh`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ refresh_token: refresh }),
    });
    if (!response.ok) return false;
    const data = await response.json();
    localStorage.setItem('fh_access_token', data.access_token);
    localStorage.setItem('fh_refresh_token', data.refresh_token);
    return true;
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
    try { await api.post('/auth/logout'); } catch (e) { /* ignore */ }
    localStorage.removeItem('fh_access_token');
    localStorage.removeItem('fh_refresh_token');
    localStorage.removeItem('fh_token_type');
    window.location.href = 'login.html';
  },
};
