(() => {
  const state=window.EXPATUS_HOME_STATE||{authenticated:false,favorites:[]};
  const csrf=document.querySelector('meta[name="csrf-token"]')?.content||'';
  const preview=csrf==='static-preview-token';
  const cards=[...document.querySelectorAll('.platform-card')];
  const search=document.querySelector('#platform-search');
  const typeSelect=document.querySelector('#platform-type');
  const priceSelect=document.querySelector('#platform-price');
  const cityBtns=[...document.querySelectorAll('.filter-tab')];
  const count=document.querySelector('.platform-section-title .count');
  const disclosure=document.querySelector('#platform-disclosure-button');
  const banner=document.querySelector('#city-guides, #city-guide-banner');
  const toast=document.getElementById('home-toast');
  let selectedCity='全部城市';
  let carouselIndex=0;
  let carouselTimer=null;
  let articleIndex=0;
  let showAllPlatforms=false;
  let savedFavorites=[];
  try{savedFavorites=JSON.parse(localStorage.getItem('expatus_favorites')||'[]')}catch{}
  const favorites=new Set(preview?savedFavorites:(state.favorites||[]));

  function showToast(text){if(!toast)return;toast.textContent=text;toast.classList.add('show');clearTimeout(showToast.t);showToast.t=setTimeout(()=>toast.classList.remove('show'),1800)}
  document.querySelectorAll('.star-btn').forEach(btn=>{
    const name=btn.dataset.platform;
    btn.classList.toggle('is-favorite',favorites.has(name));
    btn.title=favorites.has(name)?'取消收藏':'收藏到“我的收藏”';
    btn.addEventListener('click',async()=>{
      if(!state.authenticated&&!preview){location.href='/auth?next=%2F%23platforms';return;}
      btn.disabled=true;
      try{
        if(preview){
          const selected=!favorites.has(name);
          if(selected)favorites.add(name);else favorites.delete(name);
          localStorage.setItem('expatus_favorites',JSON.stringify([...favorites]));
          btn.classList.toggle('is-favorite',selected);btn.title=selected?'取消收藏':'收藏到“我的收藏”';showToast(selected?'已加入我的收藏':'已取消收藏');
          return;
        }
        const res=await fetch('/api/favorites/toggle',{method:'POST',headers:{'Content-Type':'application/json','X-CSRF-Token':csrf},body:JSON.stringify({platform:name})});
        const data=await res.json(); if(!res.ok)throw new Error(data.error||'保存失败');
        if(data.favorite)favorites.add(name);else favorites.delete(name);
        btn.classList.toggle('is-favorite',data.favorite);btn.title=data.favorite?'取消收藏':'收藏到“我的收藏”';showToast(data.favorite?'已加入我的收藏':'已取消收藏');
      }catch(err){showToast(err.message||'保存失败，请重试');}finally{btn.disabled=false;}
    });
  });

  const guideCards=[
    {city:'莱顿',key:'leiden',eyebrow:'城市租房指南 · Leiden',title:'在莱顿找房？先看清不同渠道',description:'ROOM、DUWO、私人市场与周边通勤区域。',href:'/city/leiden',action:'查看莱顿指南 →'},
    {city:'海牙',key:'den-haag',eyebrow:'城市租房指南 · Den Haag',title:'在海牙找房？先看住房规则',description:'住房许可、学生住房、常用平台与通勤区域。',href:'/city/den-haag',action:'查看海牙指南 →'}
  ];

  function renderGuide(guide){
    if(!banner||!guide)return;
    const title=banner.querySelector('.city-guide-title'),desc=banner.querySelector('.city-guide-desc'),eyebrow=banner.querySelector('.city-guide-eyebrow'),action=banner.querySelector('#city-guide-cta');
    banner.dataset.city=guide.key;
    if(title)title.textContent=guide.title;
    if(desc)desc.textContent=guide.description;
    if(eyebrow)eyebrow.textContent=guide.eyebrow;
    if(action){action.href=guide.href;action.textContent=guide.action;}
    banner.querySelectorAll('.city-carousel-dots button').forEach(dot=>dot.classList.toggle('active',dot.dataset.city===guide.key));
  }

  function stopRotation(){if(carouselTimer!==null){clearInterval(carouselTimer);carouselTimer=null;}}
  function startRotation(){
    stopRotation();
    if(window.matchMedia?.('(prefers-reduced-motion: reduce)').matches)return;
    carouselTimer=setInterval(()=>{carouselIndex=(carouselIndex+1)%guideCards.length;renderGuide(guideCards[carouselIndex]);},6000);
  }

  function updateBanner(){
    if(!banner)return;
    const dots=banner.querySelector('.city-carousel-dots');
    banner.style.display='flex';
    if(selectedCity==='全部城市'){
      if(dots)dots.hidden=false;
      renderGuide(guideCards[carouselIndex]);
      startRotation();
      return;
    }
    stopRotation();
    if(dots)dots.hidden=true;
    const guide=guideCards.find(item=>item.city===selectedCity);
    if(guide){renderGuide(guide);return;}
    renderGuide({key:'generic',eyebrow:`城市找房 · ${selectedCity}`,title:`${selectedCity}租房：先制定适合你的策略`,description:'专属城市指南正在整理，可以先按你的身份、预算和入住时间梳理行动。',href:`/workspace/strategy?city=${encodeURIComponent(selectedCity)}`,action:`生成${selectedCity}找房策略 →`});
  }
  function applyFilters(resetDisclosure=false){
    if(resetDisclosure)showAllPlatforms=false;
    const q=(search?.value||'').trim().toLowerCase(), type=typeSelect?.value||'all', price=priceSelect?.value||'all';let matched=0;
    cards.forEach(card=>{
      const text=card.textContent.toLowerCase(),cities=(card.dataset.cities||'').split('|');
      const matches=(!q||text.includes(q))&&(type==='all'||type===card.dataset.type)&&(selectedCity==='全部城市'||cities.includes('全部城市')||cities.includes(selectedCity))&&(price==='all'||price===card.dataset.price);
      if(matches)matched++;
      card.classList.toggle('is-filtered-out',!matches||(!showAllPlatforms&&matched>10));
    });
    if(count)count.textContent=matched;
    if(disclosure){
      disclosure.hidden=matched<=10;
      disclosure.textContent=matched<=10?'全部平台已显示':showAllPlatforms?'收起平台列表 ↑':`展开其余 ${matched-10} 个平台 ↓`;
      disclosure.setAttribute('aria-expanded',String(showAllPlatforms));
    }
    updateBanner();
  }
  cityBtns.forEach(btn=>btn.addEventListener('click',()=>{cityBtns.forEach(b=>b.classList.remove('active'));btn.classList.add('active');selectedCity=btn.textContent.trim();applyFilters(true);}));
  disclosure?.addEventListener('click',()=>{showAllPlatforms=!showAllPlatforms;applyFilters();if(!showAllPlatforms)document.querySelector('#platforms')?.scrollIntoView({behavior:'smooth',block:'start'});});
  banner?.querySelectorAll('.city-carousel-dots button').forEach(dot=>dot.addEventListener('click',()=>{const next=guideCards.findIndex(item=>item.key===dot.dataset.city);if(next<0)return;carouselIndex=next;renderGuide(guideCards[carouselIndex]);if(selectedCity==='全部城市')startRotation();}));
  banner?.addEventListener('mouseenter',stopRotation);
  banner?.addEventListener('mouseleave',()=>{if(selectedCity==='全部城市')startRotation();});
  const articles=[...document.querySelectorAll('.sidebar-knowledge-link')];
  if(articles.length>1&&!window.matchMedia?.('(prefers-reduced-motion: reduce)').matches){
    setInterval(()=>{
      articles[articleIndex].hidden=true;
      articles[articleIndex].classList.remove('is-visible');
      articleIndex=(articleIndex+1)%articles.length;
      articles[articleIndex].hidden=false;
      articles[articleIndex].classList.add('is-visible');
    },4800);
  }
  search?.addEventListener('input',()=>applyFilters(true));typeSelect?.addEventListener('change',()=>applyFilters(true));priceSelect?.addEventListener('change',()=>applyFilters(true));
  const q=new URLSearchParams(location.search).get('search');if(q&&search){search.value=q;setTimeout(()=>document.querySelector('#platforms')?.scrollIntoView(),30)}
  applyFilters();
})();
