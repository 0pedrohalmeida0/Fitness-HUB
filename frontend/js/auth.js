/* ============================================================
   Fitness Hub — Auth JavaScript
   Login e Cadastro · Conecta com FastAPI backend
   ============================================================ */

// ----- Configuração -----
// Aponte para a URL do seu backend FastAPI.
// Em dev local: http://localhost:8000
// Em prod: https://api.fitnesshub.com
const API_BASE_URL = 'http://localhost:8000';

// Onde redirecionar depois de logar/cadastrar com sucesso.
const REDIRECT_AFTER_AUTH = '/home';

// ============================================================
// Helpers
// ============================================================

/**
 * Mostra mensagem de erro no topo do form.
 */
function showFormError(message) {
  const banner = document.getElementById('form-error');
  if (!banner) return;
  banner.textContent = message;
  banner.hidden = false;
}

function clearFormError() {
  const banner = document.getElementById('form-error');
  if (!banner) return;
  banner.hidden = true;
  banner.textContent = '';
}

/**
 * Marca o botão como "carregando" (mostra spinner + desabilita).
 */
function setButtonLoading(button, isLoading) {
  if (isLoading) {
    button.classList.add('is-loading');
    button.disabled = true;
  } else {
    button.classList.remove('is-loading');
    button.disabled = false;
  }
}

/**
 * Salva os tokens no localStorage. Em produção, prefira cookies
 * httpOnly (mais seguro contra XSS). localStorage é mais simples
 * pro MVP.
 */
function saveTokens({ access_token, refresh_token, token_type }) {
  localStorage.setItem('fh_access_token', access_token);
  if (refresh_token) {
    localStorage.setItem('fh_refresh_token', refresh_token);
  }
  localStorage.setItem('fh_token_type', token_type || 'bearer');
}

/**
 * Marca um input com erro (borda vermelha + hint).
 */
function markFieldError(input, message) {
  const wrapper = input.closest('.field-input');
  if (wrapper) wrapper.classList.add('has-error');

  const field = input.closest('.field');
  if (field) {
    const hint = field.querySelector('.field-hint');
    if (hint && message) {
      hint.textContent = message;
      hint.classList.add('error');
    }
  }
}

function clearFieldErrors() {
  document.querySelectorAll('.field-input.has-error').forEach((el) => {
    el.classList.remove('has-error');
  });
  document.querySelectorAll('.field-hint.error').forEach((el) => {
    el.classList.remove('error');
    // Restaura o hint original — para simplicidade, o backend
    // é a fonte da verdade e o hint será re-setado se precisar.
  });
}

// ============================================================
// Validações client-side
// ============================================================

const VALIDATION = {
  username: {
    regex: /^[a-zA-Z0-9_.]+$/,
    min: 3,
    max: 50,
  },
  password: {
    min: 8,
  },
  email: {
    // Regex simples. O backend vai validar de novo com Pydantic.
    regex: /^[^\s@]+@[^\s@]+\.[^\s@]+$/,
  },
};

function validateUsername(value) {
  if (!value) return 'Informe um usuário.';
  if (value.length < VALIDATION.username.min) {
    return `Mínimo de ${VALIDATION.username.min} caracteres.`;
  }
  if (value.length > VALIDATION.username.max) {
    return `Máximo de ${VALIDATION.username.max} caracteres.`;
  }
  if (!VALIDATION.username.regex.test(value)) {
    return 'Use apenas letras, números, ponto ou underline.';
  }
  return null;
}

function validateEmail(value) {
  if (!value) return 'Informe um email.';
  if (!VALIDATION.email.regex.test(value)) return 'Email inválido.';
  return null;
}

function validatePassword(value) {
  if (!value) return 'Informe uma senha.';
  if (value.length < VALIDATION.password.min) {
    return `Mínimo de ${VALIDATION.password.min} caracteres.`;
  }
  return null;
}

// ============================================================
// API calls
// ============================================================

async function apiLogin(emailOrUsername, password) {
  const response = await fetch(`${API_BASE_URL}/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      email_or_username: emailOrUsername,
      password,
    }),
  });

  if (!response.ok) {
    // Tenta extrair a mensagem de erro do FastAPI
    let message = 'Email/usuário ou senha incorretos.';
    try {
      const data = await response.json();
      if (data.detail) message = data.detail;
    } catch (e) { /* ignore */ }
    throw new Error(message);
  }

  return response.json();
}

async function apiRegister({ username, email, password }) {
  const response = await fetch(`${API_BASE_URL}/auth/register`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ username, email, password }),
  });

  if (!response.ok) {
    let message = 'Não foi possível criar a conta. Tente novamente.';
    try {
      const data = await response.json();
      if (data.detail) {
        // FastAPI às vezes retorna detail como string, às vezes como array
        message = Array.isArray(data.detail)
          ? data.detail.map((d) => d.msg).join(', ')
          : data.detail;
      }
    } catch (e) { /* ignore */ }
    throw new Error(message);
  }

  return response.json();
}

// ============================================================
// Handlers dos forms
// ============================================================

async function handleLogin(event) {
  event.preventDefault();
  clearFormError();
  clearFieldErrors();

  const form = event.currentTarget;
  const button = form.querySelector('button[type="submit"]');
  const emailInput = form.querySelector('#login-email');
  const passInput = form.querySelector('#login-pass');

  const emailOrUsername = emailInput.value.trim();
  const password = passInput.value;

  // Validação
  let hasError = false;
  if (!emailOrUsername) {
    markFieldError(emailInput, 'Informe seu email ou usuário.');
    hasError = true;
  }
  if (!password) {
    markFieldError(passInput, 'Informe sua senha.');
    hasError = true;
  }
  if (hasError) return;

  // Submit
  setButtonLoading(button, true);
  try {
    const data = await apiLogin(emailOrUsername, password);
    saveTokens(data);
    window.location.href = REDIRECT_AFTER_AUTH;
  } catch (err) {
    showFormError(err.message);
    setButtonLoading(button, false);
  }
}

async function handleRegister(event) {
  event.preventDefault();
  clearFormError();
  clearFieldErrors();

  const form = event.currentTarget;
  const button = form.querySelector('button[type="submit"]');
  const userInput = form.querySelector('#reg-user');
  const emailInput = form.querySelector('#reg-email');
  const passInput = form.querySelector('#reg-pass');
  const termsInput = form.querySelector('input[name="accept_terms"]');

  const username = userInput.value.trim();
  const email = emailInput.value.trim();
  const password = passInput.value;

  // Validação
  const userErr = validateUsername(username);
  if (userErr) { markFieldError(userInput, userErr); }
  const emailErr = validateEmail(email);
  if (emailErr) { markFieldError(emailInput, emailErr); }
  const passErr = validatePassword(password);
  if (passErr) { markFieldError(passInput, passErr); }

  if (!termsInput.checked) {
    showFormError('Você precisa aceitar os Termos de Uso.');
    return;
  }

  if (userErr || emailErr || passErr) return;

  // Submit
  setButtonLoading(button, true);
  try {
    const data = await apiRegister({ username, email, password });
    saveTokens(data);
    window.location.href = REDIRECT_AFTER_AUTH;
  } catch (err) {
    showFormError(err.message);
    setButtonLoading(button, false);
  }
}

// ============================================================
// Inicialização
// ============================================================

document.addEventListener('DOMContentLoaded', () => {
  // Se já tá logado, manda direto pro home
  if (localStorage.getItem('fh_access_token')) {
    window.location.href = REDIRECT_AFTER_AUTH;
    return;
  }

  // Password toggle
  document.querySelectorAll('[data-toggle-password]').forEach((btn) => {
    btn.addEventListener('click', () => {
      const input = document.getElementById(btn.getAttribute('data-toggle-password'));
      if (!input) return;
      const isPassword = input.type === 'password';
      input.type = isPassword ? 'text' : 'password';
      btn.querySelector('.eye-show').hidden = isPassword;
      btn.querySelector('.eye-hide').hidden = !isPassword;
    });
  });

  // Forms
  const loginForm = document.getElementById('login-form');
  if (loginForm) loginForm.addEventListener('submit', handleLogin);

  const registerForm = document.getElementById('register-form');
  if (registerForm) registerForm.addEventListener('submit', handleRegister);

  // Social login (placeholder — implementar OAuth depois)
  document.querySelectorAll('[data-social]').forEach((btn) => {
    btn.addEventListener('click', () => {
      const provider = btn.getAttribute('data-social');
      showFormError(`Login com ${provider} ainda não implementado. Use email e senha por enquanto.`);
    });
  });
});
