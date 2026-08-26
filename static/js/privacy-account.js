/* Offer the signed-in user a direct account-erasure mechanism. */
(() => {
  const button = document.getElementById('expatus-delete-account');
  if (!button) return;
  button.addEventListener('click', async () => {
    if (!window.confirm('确认删除账户及全部找房进度、收藏和策略记录？删除后无法恢复。')) return;
    button.disabled = true;
    try {
      const response = await fetch('/api/account', {
        method: 'DELETE',
        headers: {'X-CSRF-Token': document.querySelector('meta[name="csrf-token"]')?.content || ''}
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.error || '账户删除失败。');
      window.alert(data.message || '账户已经删除。');
      window.location.href = '/';
    } catch (error) {
      button.disabled = false;
      window.alert(error.message || '账户删除失败，请联系我们。');
    }
  });
})();
