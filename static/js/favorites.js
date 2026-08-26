/* Keep authenticated favorites synchronized with account-owned server data. */
(() => {
  const csrf = document.querySelector('meta[name="csrf-token"]')?.content || '';
  const grid = document.getElementById('favorites-grid');
  const count = document.getElementById('favorite-count');
  const toast = document.getElementById('favorites-toast');

  function notify(message) {
    if (!toast) return;
    toast.textContent = message;
    toast.classList.add('show');
    setTimeout(() => toast.classList.remove('show'), 1500);
  }

  function refreshCount() {
    const remaining = grid?.querySelectorAll('.favorite-card').length || 0;
    if (count) count.textContent = String(remaining);
    if (!remaining && grid && !grid.querySelector('.empty-favs')) {
      const note = document.createElement('p');
      note.className = 'empty-favs';
      note.textContent = '还没有收藏的平台。可以回首页继续浏览。';
      grid.appendChild(note);
    }
  }

  grid?.addEventListener('click', async event => {
    const button = event.target.closest('.remove-favorite');
    if (!button) return;
    const card = button.closest('.favorite-card');
    if (!card) return;
    button.disabled = true;
    try {
      const response = await fetch('/api/favorites/toggle', {
        method: 'POST',
        headers: {'Content-Type': 'application/json', 'X-CSRF-Token': csrf},
        body: JSON.stringify({platform: card.dataset.platform})
      });
      const result = await response.json();
      if (!response.ok) throw new Error(result.error || '取消收藏失败。');
      card.remove();
      refreshCount();
      notify('已取消收藏');
    } catch (error) {
      button.disabled = false;
      notify(error.message || '取消收藏失败，请稍后重试。');
    }
  });

  refreshCount();
})();
