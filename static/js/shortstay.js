/* Shortstay read-only public catalog. No requests start scrapers. */
(() => {
  "use strict";
  const market=document.getElementById("ss-market");
  const status=document.getElementById("ss-status");
  const results=document.getElementById("ss-results");
  const buttons=[...document.querySelectorAll(".ss-tabs button")];
  if(!market||!status||!results||!buttons.length)return;
  let mode="today", pending=null;
  const el=(tag,cls,text)=>{
    const n=document.createElement(tag);
    if(cls)n.className=cls;
    if(text!==undefined&&text!==null)n.textContent=String(text);
    return n;
  };
  const price=n=>typeof n==="number"&&Number.isFinite(n)
    ?new Intl.NumberFormat("nl-NL",{style:"currency",currency:"EUR",maximumFractionDigits:0}).format(n)
    :"价格请见原帖";
  function createCard(item){
    const article=el("article","ss-card");
    const imageWrap=el("div","ss-thumbnail");
    if(item.image_url&&/^https:\/\//i.test(item.image_url)){
      const img=el("img","ss-image");
      img.src=item.image_url;
      img.loading="lazy";
      img.alt="房源照片";
      img.referrerPolicy="no-referrer";
      img.addEventListener("error",()=>imageWrap.replaceChildren(el("span","","暂无房源图片")));
      imageWrap.append(img);
    }else imageWrap.append(el("span","","暂无房源图片"));
    article.append(imageWrap);
    const body=el("div","ss-card-body");
    body.append(el("p","ss-freshness",item.freshness+" · "+item.age_band));
    body.append(el("h3","ss-title",item.title||"临时房源"));
    body.append(el("p","ss-place",[item.city,item.address].filter(Boolean).join(" · ")));
    const facts=el("div","ss-facts");
    facts.append(el("span","ss-price",price(item.price_eur)));
    if(item.start_date||item.end_date)
      facts.append(el("span","ss-dates",(item.start_date||"待确认")+" → "+(item.end_date||"待确认")));
    body.append(facts);
    if(item.summary)body.append(el("p","ss-summary",item.summary));
    const link=el("a","ss-original","打开原帖 ↗");
    link.href=item.original_url;
    link.target="_blank";
    link.rel="noopener noreferrer";
    body.append(link);
    article.append(body);
    return article;
  }
  function render(items){
    results.replaceChildren();
    let last=null,grid=null;
    for(const item of items){
      const group=item.city_group||item.city;
      if(group!==last){
        const section=el("section","ss-city-section");
        section.append(el("h2","ss-city-title",item.city));
        grid=el("div","ss-card-grid");
        section.append(grid);
        results.append(section);
        last=group;
      }
      grid.append(createCard(item));
    }
  }
  async function load(){
    if(pending)pending.abort();
    pending=new AbortController();
    const current=pending;
    results.replaceChildren();
    status.textContent="正在查询房源数据库……";
    const params=new URLSearchParams({market:market.value,mode});
    try{
      const response=await fetch("/api/shortstay/listings?"+params,{signal:current.signal});
      if(!response.ok)throw Error("HTTP "+response.status);
      const data=await response.json();
      if(!data.configured){status.textContent="短租栏目准备中：房源数据库尚未接入。";return;}
      const items=data.items||[];
      status.textContent=market.options[market.selectedIndex].text+" · "+
        (mode==="today"?"今日新发现":"最近30天")+" · "+items.length+"条";
      if(!items.length){results.append(el("div","ss-empty","目前没有符合筛选条件的房源。"));return;}
      render(items);
    }catch(e){
      if(e.name==="AbortError")return;
      status.textContent="房源信息暂时无法读取，请稍后再试。";
    }
  }
  for(const button of buttons)button.addEventListener("click",()=>{
    mode=button.dataset.mode;
    for(const tab of buttons){
      const active=tab===button;
      tab.classList.toggle("is-active",active);
      tab.setAttribute("aria-pressed",String(active));
    }
    load();
  });
  market.addEventListener("change",load);
  load();
})();
