/* ============================================================
   Fitness Hub — Home (perfil)
   ============================================================ */

// ============================================================
// Helpers de DOM (anti-XSS)
// ============================================================
function el(tag, attrs = {}, children = []) {
  const node = document.createElement(tag);
  for (const [key, value] of Object.entries(attrs)) {
    if (value == null) continue;
    if (key === 'class') node.className = value;
    else if (key === 'text') node.textContent = value;
    else if (key === 'html') console.warn('[el] opção `html` removida por segurança.');
    else if (key.startsWith('on') && typeof value === 'function') {
      node.addEventListener(key.slice(2).toLowerCase(), value);
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

function elUnsafe(htmlString) {
  const tpl = document.createElement('template');
  tpl.innerHTML = htmlString;
  return tpl.content.cloneNode(true);
}

// Ícones SVG hardcoded (sem dados de usuário)
const ICON_HEART = (filled) => `<svg viewBox="0 0 24 24" fill="${filled ? 'currentColor' : 'none'}" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 0 0-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 0 0 0-7.78z"/></svg>`;
const ICON_COMMENT = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg>`;

let profileData = null;

async function loadProfile() {
  const container = document.getElementById('profile-container');
  container.replaceChildren(el('p', { class: 'feed-empty', text: 'Carregando...' }));

  try {
    const me = await api.get('/users/me');
    profileData = me;
    renderProfile(me);

    // Carrega os posts
    const postsData = await api.get(`/users/${me.username}/posts`);
    renderPosts(postsData.items, container);
  } catch (e) {
    container.appendChild(el('p', { class: 'feed-empty', text: `Erro: ${e.message}` }));
  }
}

function renderProfile(p) {
  const container = document.getElementById('profile-container');
  container.replaceChildren();

  // Header
  const header = el('div', { class: 'profile-header' });
  const avatar = el('div', { class: 'profile-avatar', text: p.username.charAt(0).toUpperCase() });
  header.appendChild(avatar);
  header.appendChild(el('div', { class: 'profile-username', text: `@${p.username}` }));

  if (p.nome_completo) {
    header.appendChild(el('div', { style: 'color:#71717A;font-size:14px;margin-bottom:8px;', text: p.nome_completo }));
  }
  if (p.bio) {
    header.appendChild(el('div', { class: 'profile-bio', text: p.bio }));
  }

  // Stats
  const stats = el('div', { class: 'profile-stats' });
  [
    { value: p.posts_count, label: 'posts' },
    { value: p.followers_count, label: 'seguidores' },
    { value: p.following_count, label: 'seguindo' },
  ].forEach(s => {
    const stat = el('div', { class: 'profile-stat' });
    stat.appendChild(el('div', { class: 'value', text: s.value }));
    stat.appendChild(el('div', { class: 'label', text: s.label }));
    stats.appendChild(stat);
  });
  header.appendChild(stats);

  // Actions
  const actions = el('div', { class: 'profile-actions' });
  const editBtn = el('button', { type: 'button', id: 'btn-edit' });
  editBtn.appendChild(document.createTextNode('Editar perfil'));
  editBtn.addEventListener('click', openEditModal);
  actions.appendChild(editBtn);

  if (p.is_private) {
    const priv = el('span', { class: 'private-badge', text: '🔒 Conta privada' });
    actions.appendChild(priv);
  }
  if (p.is_admin) {
    const admin = el('span', { class: 'private-badge', text: '⚙ Admin', style: 'background:rgba(163,230,53,0.15);color:#65A30D;border-color:#65A30D;' });
    actions.appendChild(admin);
  }
  header.appendChild(actions);

  container.appendChild(header);

  // Posts title
  const postsTitle = el('h2', { class: 'profile-posts-title', text: 'Meus posts' });
  container.appendChild(postsTitle);
}

function renderPosts(posts, container) {
  // Remove posts anteriores
  container.querySelectorAll('.post-card, .feed-empty').forEach(el => el.remove());

  if (posts.length === 0) {
    const empty = el('p', { class: 'feed-empty', text: 'Você ainda não postou nada. Crie seu primeiro post!' });
    container.appendChild(empty);
    return;
  }

  posts.forEach(p => {
    container.appendChild(buildPostCard(p));
  });
}

function buildPostCard(p) {
  const card = el('article', { class: 'post-card', 'data-post-id': p.id });

  // Header
  const header = el('div', { class: 'post-header' });
  const avatar = el('div', { class: 'post-avatar', text: (p.autor_username || '?').charAt(0).toUpperCase() });
  header.appendChild(avatar);
  const authorInfo = el('div');
  authorInfo.appendChild(el('div', { class: 'post-author', text: `@${p.autor_username}` }));
  const timeRow = el('div', { class: 'post-time' });
  timeRow.appendChild(document.createTextNode(formatTime(p.created_at)));
  if (p.is_private) {
    timeRow.appendChild(el('span', { class: 'post-private-badge', text: 'privado' }));
  }
  authorInfo.appendChild(timeRow);
  header.appendChild(authorInfo);
  card.appendChild(header);

  // Conteúdo
  card.appendChild(el('div', { class: 'post-text', text: p.legenda }));

  // Ações
  const actions = el('div', { class: 'post-actions' });
  const likeBtn = el('button', {
    class: p.user_like_count > 0 ? 'post-action liked' : 'post-action',
    type: 'button',
    'data-like': p.id,
  });
  // SVG hardcoded (sem dados de usuário) — seguro usar elUnsafe
  likeBtn.appendChild(elUnsafe(ICON_HEART(p.user_like_count > 0)));
  likeBtn.appendChild(document.createTextNode(` ${p.likes_count || ''}`));
  likeBtn.addEventListener('click', () => handleLike(p.id, likeBtn, p));
  actions.appendChild(likeBtn);

  const commentBtn = el('button', { class: 'post-action', type: 'button', 'data-comments': p.id });
  commentBtn.appendChild(elUnsafe(ICON_COMMENT));
  commentBtn.appendChild(document.createTextNode(` ${p.comments_count || ''}`));
  commentBtn.addEventListener('click', () => toggleComments(p.id, card));
  actions.appendChild(commentBtn);

  card.appendChild(actions);

  // Comments section (inicialmente oculta)
  const commentsSection = el('div', { class: 'comments-section', id: `comments-${p.id}`, hidden: true });
  card.appendChild(commentsSection);

  return card;
}

function formatTime(iso) {
  if (!iso) return '';
  const d = new Date(iso);
  const now = new Date();
  const diffMs = now - d;
  const diffMin = Math.floor(diffMs / 60000);
  if (diffMin < 1) return 'agora';
  if (diffMin < 60) return `há ${diffMin} min`;
  const diffH = Math.floor(diffMin / 60);
  if (diffH < 24) return `há ${diffH} h`;
  const diffD = Math.floor(diffH / 24);
  if (diffD < 7) return `há ${diffD} d`;
  return d.toLocaleDateString('pt-BR');
}

async function handleLike(postId, btn, post) {
  try {
    if (post.user_like_count > 0) {
      // Unlike (remove 1)
      await api.del(`/posts/${postId}/like`);
      post.user_like_count -= 1;
      post.likes_count = Math.max(0, (post.likes_count || 0) - 1);
    } else {
      // Like
      await api.post(`/posts/${postId}/like`, {});
      post.user_like_count += 1;
      post.likes_count = (post.likes_count || 0) + 1;
    }
    // Atualiza UI
    btn.className = post.user_like_count > 0 ? 'post-action liked' : 'post-action';
    btn.lastChild.textContent = ` ${post.likes_count || ''}`;
  } catch (e) {
    alert('Erro: ' + e.message);
  }
}

async function toggleComments(postId, card) {
  const section = document.getElementById(`comments-${postId}`);
  if (!section.hidden) {
    section.hidden = true;
    return;
  }
  section.hidden = false;
  section.replaceChildren(el('p', { style: 'color:#A1A1AA;font-size:13px;', text: 'Carregando comentários...' }));

  try {
    const comments = await api.get(`/posts/${postId}/comments`);
    section.replaceChildren();
    if (comments.length === 0) {
      section.appendChild(el('p', { style: 'color:#A1A1AA;font-size:13px;', text: 'Nenhum comentário ainda.' }));
    } else {
      comments.forEach(c => section.appendChild(buildComment(c, postId)));
    }
    // Form pra adicionar
    section.appendChild(buildCommentForm(postId));
  } catch (e) {
    section.appendChild(el('p', { style: 'color:#DC2626;font-size:13px;', text: `Erro: ${e.message}` }));
  }
}

function buildComment(c, postId) {
  const wrap = el('div', { class: 'comment', 'data-comment-id': c.id });
  wrap.appendChild(el('div', { class: 'comment-avatar', text: (c.autor_username || '?').charAt(0).toUpperCase() }));

  const body = el('div', { class: 'comment-body' });
  const header = el('div', { class: 'comment-header' });
  header.appendChild(el('span', { class: 'comment-author', text: `@${c.autor_username}` }));
  header.appendChild(el('span', { class: 'comment-time', text: formatTime(c.created_at) }));
  body.appendChild(header);
  body.appendChild(el('div', { class: 'comment-text', text: c.conteudo }));
  wrap.appendChild(body);
  return wrap;
}

function buildCommentForm(postId) {
  const form = el('div', { class: 'comment-form' });
  const input = el('input', { type: 'text', placeholder: 'Comentar...', maxlength: '2000' });
  const send = el('button', { type: 'button', text: 'Enviar' });
  send.disabled = true;
  input.addEventListener('input', () => { send.disabled = !input.value.trim(); });
  send.addEventListener('click', async () => {
    const text = input.value.trim();
    if (!text) return;
    send.disabled = true;
    try {
      const c = await api.post(`/posts/${postId}/comments`, { conteudo: text });
      input.value = '';
      const section = document.getElementById(`comments-${postId}`);
      const newComment = buildComment(c, postId);
      section.insertBefore(newComment, form);
    } catch (e) {
      alert('Erro: ' + e.message);
    }
  });
  form.appendChild(input);
  form.appendChild(send);
  return form;
}

// ----- Edit profile modal -----
function openEditModal() {
  if (!profileData) return;
  document.getElementById('edit-nome').value = profileData.nome_completo || '';
  document.getElementById('edit-bio').value = profileData.bio || '';
  document.getElementById('edit-private').checked = profileData.is_private;
  document.getElementById('edit-modal').hidden = false;
}

function closeEditModal() {
  document.getElementById('edit-modal').hidden = true;
}

document.addEventListener('DOMContentLoaded', () => {
  document.getElementById('logout-link').addEventListener('click', (e) => {
    e.preventDefault();
    authApi.logout();
  });
  document.getElementById('btn-cancel-edit').addEventListener('click', closeEditModal);
  document.getElementById('edit-modal').addEventListener('click', (e) => {
    if (e.target.id === 'edit-modal') closeEditModal();
  });
  document.getElementById('btn-save-edit').addEventListener('click', async () => {
    const payload = {
      nome_completo: document.getElementById('edit-nome').value.trim() || null,
      bio: document.getElementById('edit-bio').value.trim() || null,
      is_private: document.getElementById('edit-private').checked,
    };
    try {
      await api.patch('/users/me', payload);
      closeEditModal();
      await loadProfile();
    } catch (e) {
      alert('Erro: ' + e.message);
    }
  });
  loadProfile();
});
