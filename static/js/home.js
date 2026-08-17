(() => {
  const state=window.EXPATUS_HOME_STATE||{authenticated:false,favorites:[]};
  const csrf=document.querySelector('meta[name="csrf-token"]')?.content||'';
  const cards=[...document.querySelectorAll('.platform-card')];
  const search=document.querySelector('#platform-search');
  const typeSelect=document.querySelector('#platform-type');
  const priceSelect=document.querySelector('#platform-price');
  const cityBtns=[...document.querySelectorAll('.filter-tab')];
  const count=document.querySelector('.platform-section-title .count');
  const banner=document.querySelector('#city-guide-banner');
  const toast=document.getElementById('home-toast');
  let selectedCity='全部城市';
  const favorites=new Set(state.favorites||[]);

  function showToast(text){if(!toast)return;toast.textContent=text;toast.classList.add('show');clearTimeout(showToast.t);showToast.t=setTimeout(()=>toast.classList.remove('show'),1800)}
  document.querySelectorAll('.star-btn').forEach(btn=>{
    const name=btn.dataset.platform;
    btn.classList.toggle('is-favorite',favorites.has(name));
    btn.title=favorites.has(name)?'取消收藏':'收藏到“我的收藏”';
    btn.addEventListener('click',async()=>{
      if(!state.authenticated){location.href='/auth?next=%2F%23platforms';return;}
      btn.disabled=true;
      try{
        const res=await fetch('/api/favorites/toggle',{method:'POST',headers:{'Content-Type':'application/json','X-CSRF-Token':csrf},body:JSON.stringify({platform:name})});
        const data=await res.json(); if(!res.ok)throw new Error(data.error||'保存失败');
        if(data.favorite)favorites.add(name);else favorites.delete(name);
        btn.classList.toggle('is-favorite',data.favorite);btn.title=data.favorite?'取消收藏':'收藏到“我的收藏”';showToast(data.favorite?'已加入我的收藏':'已取消收藏');
      }catch(err){showToast(err.message||'保存失败，请重试');}finally{btn.disabled=false;}
    });
  });

  function updateBanner(){
    if(!banner)return;
    const title=banner.querySelector('.city-guide-title'), desc=banner.querySelector('.city-guide-desc'), eyebrow=banner.querySelector('.city-guide-eyebrow'), link=banner.querySelector('a');
    if(selectedCity==='全部城市'){banner.style.display='flex';eyebrow.textContent='📍 城市租房指南';title.textContent='第一次在莱顿找房？';desc.textContent='学生住房、私人市场、常用平台和周边通勤区域，集中整理在这一页。';link.textContent='查看莱顿指南 →';}
    else if(selectedCity==='莱顿'){banner.style.display='flex';eyebrow.textContent='📍 莱顿租房指南';title.textContent='ROOM、DUWO、私人市场和周边通勤区域';desc.textContent='莱顿常用找房资源和不同住房路径，集中整理在这一页。';link.textContent='打开完整指南 →';}
    else banner.style.display='none';
  }
  function applyFilters(){
    const q=(search?.value||'').trim().toLowerCase(), type=typeSelect?.value||'all', price=priceSelect?.value||'all';let shown=0;
    cards.forEach(card=>{const text=card.textContent.toLowerCase(), cities=(card.dataset.cities||'').split('|');const show=(!q||text.includes(q))&&(type==='all'||type===card.dataset.type)&&(selectedCity==='全部城市'||cities.includes('全部城市')||cities.includes(selectedCity))&&(price==='all'||price===card.dataset.price);card.classList.toggle('is-filtered-out',!show);if(show)shown++;});
    if(count)count.textContent=shown;updateBanner();
  }
  cityBtns.forEach(btn=>btn.addEventListener('click',()=>{cityBtns.forEach(b=>b.classList.remove('active'));btn.classList.add('active');selectedCity=btn.textContent.trim();applyFilters();}));
  search?.addEventListener('input',applyFilters);typeSelect?.addEventListener('change',applyFilters);priceSelect?.addEventListener('change',applyFilters);
  const q=new URLSearchParams(location.search).get('search');if(q&&search){search.value=q;setTimeout(()=>document.querySelector('#platforms')?.scrollIntoView(),30)}
  applyFilters();
})();
