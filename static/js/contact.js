(() => {
  const csrf = document.querySelector('meta[name="csrf-token"]')?.content || '';
  const form = document.getElementById('contactForm');
  const chips = [...document.querySelectorAll('#contactChips button')];
  const submit = document.getElementById('contactSubmit');
  const status = document.getElementById('contactStatus');
  let category = '网站建议';

  chips.forEach(btn => btn.addEventListener('click', () => {
    chips.forEach(x => x.classList.remove('active'));
    btn.classList.add('active');
    category = btn.dataset.value;
  }));

  form.addEventListener('submit', async e => {
    e.preventDefault();
    const message = form.message.value.trim();
    if (message.length < 5) {
      status.className = 'contact-status error';
      status.textContent = '请至少写几句话告诉我们你的留言。';
      return;
    }
    const payload = {
      category,
      subject: form.subject.value.trim(),
      message,
      email: form.email.value.trim(),
      wechat: form.wechat.value.trim()
    };
    submit.disabled = true;
    submit.textContent = '提交中…';
    status.className = 'contact-status';
    status.textContent = '';
    try {
      const r = await fetch('/api/contact', {
        method: 'POST',
        headers: {'Content-Type':'application/json','X-CSRF-Token':csrf},
        body: JSON.stringify(payload)
      });
      const d = await r.json();
      if (!r.ok) throw new Error(d.error || '提交失败，请稍后重试。');
      submit.textContent = '✓ 已收到';
      status.className = 'contact-status success';
      status.textContent = '留言已经收到，谢谢你。';
      form.reset();
      category = '网站建议';
      chips.forEach((x,i) => x.classList.toggle('active', i === 0));
      setTimeout(() => {
        submit.disabled = false;
        submit.textContent = '提交留言';
      }, 1600);
    } catch (err) {
      submit.disabled = false;
      submit.textContent = '提交留言';
      status.className = 'contact-status error';
      status.textContent = err.message;
    }
  });
})();