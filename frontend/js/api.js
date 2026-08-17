/* ============================================================
   Fitness Hub — API client
   Autenticação via cookies httpOnly (defesa contra XSS).

   O back seta `fh_access_token` (path /) e `fh_refresh_token`
   (path /auth) no login/refresh. Como são httpOnly, o JS não
   consegue ler — mas o browser envia automaticamente em requests
   pro mesmo origin.
   ============================================================ */

const API_BASE_URL = 'http://localhost:8000';
const DEFAULT_TIMEOUT_MS = 10_000;  // 10s

/**
 * Wrapper sobre fetch com:
 * - credentials include (envia cookies httpOnly)
 * - timeout via AbortController
 * - 401 → tenta refresh automático
 * - converte erros em exceptions com mensagem útil
 */
async function apiFetch(path, options = {}) {
  const url = `${API_BASE_URL}${path}`;
  const timeoutMs = options.timeout ?? DEFAULT_TIMEOUT_MS;

  // AbortController com timeout
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), timeoutMs);

  const config = {
    credentials: 'include',
    signal: controller.signal,
    headers: {
      'Content-Type': 'application/json',
      ...(options.headers || {}),
    },
    ...options,
  };
  // signal/credentials/headers não podem ser sobrescritos pelo options cru
  config.signal = controller.signal;
  config.credentials = 'include';

  if (config.body && typeof config.body === 'object' && !(config.body instanceof FormData)) {
    config.body = JSON.stringify(config.body);
  }

  let response;
  try {
    response = await fetch(url, config);
  } catch (e) {
    clearTimeout(timeoutId);
    if (e.name === 'AbortError') {
      throw new Error(`Request timeout (${timeoutMs}ms): ${path}`);
    }
    throw e;
  }
  clearTimeout(timeoutId);

  // Token expirou — tenta refresh (apenas uma vez, mesmo com chamadas paralelas)
  if (response.status === 401 && !path.startsWith('/auth/')) {
    const refreshed = await ensureFreshToken();
    if (refreshed) {
      // Refaz com novo controller/timeout
      const ctrl2 = new AbortController();
      const t2 = setTimeout(() => ctrl2.abort(), timeoutMs);
      config.signal = ctrl2.signal;
      try {
        response = await fetch(url, config);
      } finally {
        clearTimeout(t2);
      }
    } else {
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
    const response = await fetch(`${API_BASE_URL}/auth/refresh`, {
      method: 'POST',
      credentials: 'include',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({}),
    });
    return response.ok;
  } catch (e) {
    return false;
  }
}

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
    try { await api.post('/auth/logout', {}); } catch (e) { /* ignore */ }
    localStorage.removeItem('fh_access_token');
    localStorage.removeItem('fh_refresh_token');
    localStorage.removeItem('fh_token_type');
    window.location.href = 'login.html';
  },
};
