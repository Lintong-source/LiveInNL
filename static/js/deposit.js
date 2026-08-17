(() => {
  const csrf=document.querySelector('meta[name="csrf-token"]')?.content||'';
  const chips=[...document.querySelectorAll('#issueChips button')];chips.forEach(btn=>btn.addEventListener('click',()=>btn.classList.toggle('active')));
  const form=document.getElementById('caseForm'),btn=document.getElementById('submitBtn'),message=document.getElementById('formMessage');
  form.addEventListener('submit',async e=>{
    e.preventDefault();const desc=document.getElementById('description').value.trim();if(desc.length<10){message.className='form-message error';message.textContent='请至少用几句话简单描述一下发生了什么。';return;}
    const payload={city:form.city.value.trim(),contract_date:form.contract_date.value,rental_ended:form.ended.value,moveout_date:form.moveout_date.value,base_rent:form.rent.value,deposit:form.deposit.value,issues:chips.filter(x=>x.classList.contains('active')).map(x=>x.dataset.value),checkin_report:form.checkin.value,deduction_spec:form.spec.value,description:desc,email:form.email.value.trim(),wechat:form.wechat.value.trim(),contact_ok:form.contact_ok.checked};
    btn.disabled=true;btn.textContent='提交中…';message.className='form-message';message.textContent='';
    try{const r=await fetch('/api/cases',{method:'POST',headers:{'Content-Type':'application/json','X-CSRF-Token':csrf},body:JSON.stringify(payload)}),d=await r.json();if(!r.ok)throw new Error(d.error||'提交失败，请稍后重试。');btn.textContent='✓ 已收到';message.className='form-message success';message.textContent='感谢你的分享。我们会用这些信息继续完善租房内容；如果你同意回访并留下联系方式，我们可能会联系你进一步了解。';form.reset();chips.forEach(x=>x.classList.remove('active'));setTimeout(()=>{btn.disabled=false;btn.textContent='提交问题'},1800)}catch(err){message.className='form-message error';message.textContent=err.message;btn.disabled=false;btn.textContent='提交问题'}
  });
})();
