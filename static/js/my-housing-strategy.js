/* The backend owns every strategy decision. This file only collects input and renders its contract. */
const workspaceState = window.EXPATUS_STRATEGY_STATE || {};
const DAILY_LIMIT = Number(workspaceState.daily_limit || 3);
const strategyCsrf = document.querySelector('meta[name="csrf-token"]')?.content || '';
let serverUsedToday = Number(workspaceState.used_today || 0);
let currentStrategy = workspaceState.strategy || null;
const $ = selector => document.querySelector(selector);
const $$ = selector => [...document.querySelectorAll(selector)];

function values() {
  return {
    identity: $('#identity').value,
    city: $('#city').value,
    moveDate: $('#moveDate').value,
    homeType: $('#homeType').value,
    budget: Number($('#budget').value || 0),
    income: $('#income').value,
    studentReg: $('#studentReg').value,
    universityHousing: $('#universityHousing').value,
    areaFlex: $('#areaFlex').value,
  };
}

function escapeHtml(value) {
  return String(value ?? '').replace(/[&<>"]/g, char => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;'}[char]));
}

function toast(message) {
  const element = $('#toast');
  element.textContent = message;
  element.classList.add('show');
  setTimeout(() => element.classList.remove('show'), 2200);
}

function renderStars(count) {
  return `<div class="dots">${[1, 2, 3, 4, 5].map(index => `<i class="dot ${index <= count ? 'on' : ''}"></i>`).join('')}</div>`;
}

function renderEffort(strategy) {
  const chart = $('#effortChart');
  const tooltip = $('#chartTooltip');
  $('#effortCopy').textContent = strategy.effort_copy;
  chart.innerHTML = strategy.effort.map(dataset => `
    <div class="bar-group">
      <div class="stack-bar">${dataset.rows.map(row => `
        <div class="stack-seg" data-name="${escapeHtml(row.name)}" data-mins="${row.minutes}"
          data-pct="${Math.round(row.percent)}" data-height="${row.percent}"
          data-color="${escapeHtml(row.color)}" data-action="${escapeHtml(row.action)}"></div>`).join('')}</div>
      <div class="bar-label"><b>${dataset.total}</b> 分钟</div>
    </div>`).join('');
  $$('.stack-seg').forEach(segment => {
    segment.style.height = `${segment.dataset.height}%`;
    segment.style.background = segment.dataset.color;
    segment.addEventListener('mouseenter', () => {
      tooltip.innerHTML = `<b>${escapeHtml(segment.dataset.name)}</b>${segment.dataset.mins} 分钟 · ${segment.dataset.pct}%<span>${escapeHtml(segment.dataset.action)}</span>`;
      tooltip.classList.add('show');
    });
    segment.addEventListener('mousemove', event => {
      tooltip.style.left = `${event.clientX}px`;
      tooltip.style.top = `${event.clientY}px`;
    });
    segment.addEventListener('mouseleave', () => tooltip.classList.remove('show'));
  });
  const legend = strategy.effort.at(-1)?.rows || [];
  $('#effortLegend').innerHTML = legend.map(row => `<span class="legend-item"><i class="legend-dot" data-color="${escapeHtml(row.color)}"></i>${escapeHtml(row.name)}</span>`).join('');
  $$('.legend-dot').forEach(dot => { dot.style.background = dot.dataset.color; });
}

function renderChannels(strategy) {
  $('#channelList').innerHTML = strategy.channels.map((channel, index) => `
    <article class="card channel ${escapeHtml(channel.tone)} expatus-panel" data-channel-kind="${escapeHtml(channel.kind)}">
      <div class="channel-overview">
        <div class="channel-name"><strong>${escapeHtml(channel.name)}</strong><small>${escapeHtml(channel.subtitle)}</small></div>
        <div class="priority-block"><span class="priority-label">战略价值</span>${renderStars(channel.stars)}</div>
        <div class="channel-advice"><span class="status-pill ${escapeHtml(channel.tone)}">${escapeHtml(channel.state)}</span><strong>${escapeHtml(channel.action)}</strong></div>
        <div class="work"><span class="work-label">当前投入</span><strong>${escapeHtml(channel.effort)}</strong><small>${channel.tone === 'passive' ? '低频维护' : '按阶段执行'}</small></div>
        <button class="expand-btn" type="button" aria-expanded="false" data-open="${index}">判断依据 +</button>
      </div>
      <div class="platform-strip">
        <div class="platform-strip-head"><strong>相关平台与当前动作</strong><span>${channel.platforms.length} 个平台</span></div>
        <div class="platform-list" role="list">${channel.platforms.map(platform => {
          const external = String(platform.url).startsWith('https://');
          return `<div class="platform-row" role="listitem"><div class="platform-row-main"><div class="platform-title"><strong>${escapeHtml(platform.name)}</strong><span class="mini-state ${escapeHtml(platform.tone)}">${escapeHtml(platform.state)}</span></div><p>${escapeHtml(platform.note)}</p></div><a href="${escapeHtml(platform.url)}" class="platform-link"${external ? ' target="_blank" rel="noopener noreferrer"' : ''}>${escapeHtml(platform.label)} →</a></div>`;
        }).join('')}</div>
        ${['commercial', 'operator'].includes(channel.kind) ? '<div class="platform-monitor-note"><span>后续可接入房源监控提醒</span></div>' : ''}
      </div>
      <div class="channel-expand"><div class="reason-row"><span>排序依据</span><p>${escapeHtml(channel.why)}</p></div><div class="reason-row"><span>调整时机</span><p>${escapeHtml(channel.adjust)}</p></div></div>
    </article>`).join('');
  $$('.expand-btn').forEach(button => {
    button.onclick = () => {
      const card = button.closest('.channel');
      const open = card.classList.toggle('open');
      button.setAttribute('aria-expanded', String(open));
      button.textContent = open ? '收起依据 −' : '判断依据 +';
    };
  });
}

function renderProgress(strategy) {
  const progress = strategy.progress;
  $('#pApplications').textContent = progress.applications;
  $('#pReplies').textContent = progress.replies;
  $('#pViewings').textContent = progress.viewings;
  $('#pActive').textContent = progress.active;
  $('#progressDiagnosis').innerHTML = `<b>${escapeHtml(strategy.progress_diagnosis.title)}</b> ${escapeHtml(strategy.progress_diagnosis.text)}`;
  const hasData = progress.tracked > 0;
  $('#progressState').textContent = hasData ? '已同步 · 参与判断' : '尚无记录';
  $('#progressState').className = `status-pill ${hasData ? 'daily' : 'passive'}`;
}

function render(strategy) {
  currentStrategy = strategy;
  $('#days').textContent = strategy.days;
  $('#stateIcon').textContent = strategy.status.icon;
  $('#stateTitle').textContent = strategy.status.title;
  $('#stateDesc').textContent = strategy.status.description;
  $('#profileChips').innerHTML = strategy.profile_chips.map(item => `<span>${escapeHtml(item)}</span>`).join('');
  $('#topActions').innerHTML = strategy.top_actions.map((action, index) => `<article class="action ${escapeHtml(action.tone)}"><span class="n">0${index + 1} · ${escapeHtml(action.when)}</span><strong>${escapeHtml(action.title)}</strong><span>${index === 0 ? '优先处理' : '完成后继续下一项'}</span></article>`).join('');

  const plan = strategy.plan_b;
  const planCard = $('#planBCard');
  planCard.classList.remove('planb-warn', 'planb-danger', 'planb-safe');
  planCard.classList.add(`planb-${plan.tone}`);
  $('#planBStage').textContent = plan.stage;
  $('#planBTitle').textContent = plan.title;
  $('#planBDesc').textContent = plan.description;

  renderEffort(strategy);
  renderChannels(strategy);
  renderProgress(strategy);

  $('#phaseTrack').innerHTML = strategy.phase.steps.map((step, index) => `<div class="phase-step ${index === strategy.phase.index ? 'active' : ''}"><i>${index + 1}</i><strong>${escapeHtml(step.name)}</strong><span>${escapeHtml(step.range)}</span></div>`).join('');
  $('#phaseCopy').textContent = strategy.phase.copy;
  $('#phaseTrigger').innerHTML = `<b>下一次策略变化：</b>${escapeHtml(strategy.phase.trigger)}`;
  $('#factorGrid').innerHTML = strategy.factors.map(factor => `<div class="factor"><span>${escapeHtml(factor.label)}</span><strong>${escapeHtml(factor.value)}</strong></div>`).join('');
  $('#explainText').textContent = strategy.explanation;

  $('#regenInfo').innerHTML = `今日策略生成 <b>${serverUsedToday} / ${DAILY_LIMIT}</b> · ${Math.max(0, DAILY_LIMIT - serverUsedToday)} 次可用`;
  $('#regenBtn').disabled = serverUsedToday >= DAILY_LIMIT;
}

function showResult(strategy, animated = false) {
  $('#onboarding').style.display = 'none';
  if (!animated) {
    $('#loading').classList.remove('show');
    $('#result').classList.add('show');
    render(strategy);
    return;
  }
  $('#result').classList.remove('show');
  $('#loading').classList.add('show');
  const steps = $$('.load-step');
  steps.forEach(step => step.classList.remove('active', 'done'));
  const titles = ['正在读取你的找房条件', '正在匹配对应渠道规则', '正在判断当前时间窗口', '正在生成行动优先级'];
  let index = 0;
  const timer = setInterval(() => {
    if (index > 0) {
      steps[index - 1].classList.remove('active');
      steps[index - 1].classList.add('done');
      steps[index - 1].querySelector('.ico').textContent = '✓';
    }
    if (index < steps.length) {
      steps[index].classList.add('active');
      $('#loadingTitle').textContent = titles[index];
      index += 1;
      return;
    }
    clearInterval(timer);
    setTimeout(() => {
      $('#loading').classList.remove('show');
      $('#result').classList.add('show');
      render(strategy);
      window.scrollTo({top: 245, behavior: 'smooth'});
    }, 250);
  }, 450);
}

async function generateStrategy() {
  if (serverUsedToday >= DAILY_LIMIT) {
    toast('今天的 3 次策略生成已用完，普通进度更新不受影响。');
    return;
  }
  try {
    const response = await fetch('/api/strategies/generate', {
      method: 'POST',
      headers: {'Content-Type': 'application/json', 'X-CSRF-Token': strategyCsrf},
      body: JSON.stringify(values()),
    });
    const payload = await response.json();
    if (!response.ok) throw new Error(payload.error || '策略生成失败，请稍后重试。');
    serverUsedToday = Number(payload.used_today ?? serverUsedToday + 1);
    showResult(payload.strategy, true);
  } catch (error) {
    toast(error.message || '策略生成失败，请稍后重试。');
  }
}

let syncPending = false;
async function syncStrategy({notify = false} = {}) {
  if (syncPending || !currentStrategy) return;
  syncPending = true;
  const button = $('#manageProgressBtn');
  if (notify) {
    button.disabled = true;
    button.textContent = '重新计算中…';
  }
  try {
    const response = await fetch('/api/strategies/current', {headers: {'Accept': 'application/json'}, cache: 'no-store'});
    const payload = await response.json();
    if (!response.ok) throw new Error(payload.error || '重新计算策略失败，请稍后重试。');
    render(payload.strategy);
    if (notify) toast('已按当前房源状态重新计算完整策略。');
  } catch (error) {
    if (notify) toast(error.message || '同步房源进度失败，请稍后重试。');
  } finally {
    syncPending = false;
    if (notify) {
      button.disabled = false;
      button.textContent = '同步并重新计算';
    }
  }
}

function restoreProfile(profile) {
  if (!profile) return;
  Object.entries(profile).forEach(([field, value]) => {
    const element = $(`#${field}`);
    if (element && value != null) element.value = value;
  });
}

function mountDialog() {
  const clone = $('#strategyForm').cloneNode(true);
  clone.id = 'dialogForm';
  clone.querySelector('.form-progress').remove();
  clone.querySelector('.form-footer').remove();
  clone.querySelectorAll('[id]').forEach(element => {
    const original = $(`#${element.id}`);
    if (original) element.value = original.value;
    element.id = `d_${element.id}`;
  });
  $('#dialogFormMount').innerHTML = '';
  $('#dialogFormMount').appendChild(clone);
}

$('#strategyForm').addEventListener('submit', event => { event.preventDefault(); generateStrategy(); });
$('#regenBtn').onclick = generateStrategy;
$('#manageProgressBtn').onclick = () => syncStrategy({notify: true});
$('#editBtn').onclick = () => { mountDialog(); $('#editDialog').showModal(); };
$('#closeDialog').onclick = $('#cancelEdit').onclick = () => $('#editDialog').close();
$('#saveEdit').onclick = () => {
  ['identity', 'city', 'moveDate', 'homeType', 'budget', 'income', 'studentReg', 'universityHousing', 'areaFlex'].forEach(id => { $(`#${id}`).value = $(`#d_${id}`).value; });
  $('#editDialog').close();
  toast('资料已保存。点击“重新制定策略”后才会重新计算。');
};
$('#explainToggle').onclick = () => {
  const body = $('#explainBody');
  const show = body.style.display === 'none';
  body.style.display = show ? 'block' : 'none';
  $('#explainToggle').textContent = show ? '收起依据' : '展开依据';
};

restoreProfile(workspaceState.latest_profile);
if (currentStrategy) setTimeout(() => showResult(currentStrategy), 50);
window.addEventListener?.('focus', () => syncStrategy());
window.addEventListener?.('pageshow', event => { if (event.persisted) syncStrategy(); });
