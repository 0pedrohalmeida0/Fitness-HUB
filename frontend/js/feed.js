/* ============================================================
   Fitness Hub — Feed (timeline)
   ============================================================ */

async function loadFeed() {
  const container = document.getElementById('feed-container');
  container.replaceChildren(el('p', { class: 'feed-empty', text: 'Carregando...' }));

  try {
    const data = await api.get('/feed?page_size=20');
    renderFeed(data.items, container);
  } catch (e) {
    container.appendChild(el('p', { class: 'feed-empty', text: `Erro: ${e.message}` }));
  }
}

function renderFeed(posts, container) {
  container.replaceChildren();
  if (posts.length === 0) {
    container.appendChild(el('p', {
      class: 'feed-empty',
      text: 'Ainda não há posts no seu feed. Comece a seguir pessoas!',
    }));
    return;
  }
  posts.forEach(p => container.appendChild(buildPostCard(p)));
}

function buildPostCard(p) {
  const card = el('article', { class: 'post-card', 'data-post-id': p.id });

  const header = el('div', { class: 'post-header' });
  const avatar = el('div', { class: 'post-avatar', text: (p.autor_username || '?').charAt(0).toUpperCase() });
  header.appendChild(avatar);
  const authorInfo = el('div');
  const authorLink = el('a', {
    href: `perfil.html?u=${p.autor_username}`,
    style: 'text-decoration:none;color:inherit;',
  });
  authorLink.appendChild(el('div', { class: 'post-author', text: `@${p.autor_username}` }));
  authorInfo.appendChild(authorLink);
  const timeRow = el('div', { class: 'post-time' });
  timeRow.appendChild(document.createTextNode(formatTime(p.created_at)));
  if (p.is_private) {
    timeRow.appendChild(el('span', { class: 'post-private-badge', text: 'privado' }));
  }
  authorInfo.appendChild(timeRow);
  header.appendChild(authorInfo);
  card.appendChild(header);

  card.appendChild(el('div', { class: 'post-text', text: p.legenda }));

  const actions = el('div', { class: 'post-actions' });
  const likeBtn = el('button', {
    class: p.user_like_count > 0 ? 'post-action liked' : 'post-action',
    type: 'button',
  });
  likeBtn.innerHTML = `<svg viewBox="0 0 24 24" fill="${p.user_like_count > 0 ? 'currentColor' : 'none'}" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 0 0-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 0 0 0-7.78z"/></svg>`;
  likeBtn.appendChild(document.createTextNode(` ${p.likes_count || ''}`));
  likeBtn.addEventListener('click', () => handleLike(p.id, likeBtn, p));
  actions.appendChild(likeBtn);

  const commentBtn = el('button', { class: 'post-action', type: 'button' });
  commentBtn.innerHTML = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg>`;
  commentBtn.appendChild(document.createTextNode(` ${p.comments_count || ''}`));
  commentBtn.addEventListener('click', () => toggleComments(p.id, card));
  actions.appendChild(commentBtn);

  card.appendChild(actions);

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
      await api.del(`/posts/${postId}/like`);
      post.user_like_count -= 1;
      post.likes_count = Math.max(0, (post.likes_count || 0) - 1);
    } else {
      await api.post(`/posts/${postId}/like`, {});
      post.user_like_count += 1;
      post.likes_count = (post.likes_count || 0) + 1;
    }
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

document.addEventListener('DOMContentLoaded', () => {
  document.getElementById('logout-link').addEventListener('click', (e) => {
    e.preventDefault();
    authApi.logout();
  });
  document.getElementById('btn-postar').addEventListener('click', async () => {
    const legenda = document.getElementById('post-legenda').value.trim();
    if (!legenda) {
      alert('Digite algo para postar.');
      return;
    }
    const is_private = document.getElementById('post-private').checked;
    const btn = document.getElementById('btn-postar');
    btn.disabled = true;
    try {
      await api.post('/posts', { legenda, is_private });
      document.getElementById('post-legenda').value = '';
      document.getElementById('post-private').checked = false;
      await loadFeed();
    } catch (e) {
      alert('Erro: ' + e.message);
    } finally {
      btn.disabled = false;
    }
  });
  loadFeed();
});
