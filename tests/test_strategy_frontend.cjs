/* Dependency-free check that the browser renders backend results without owning rules. */
const assert = require('assert/strict');
const fs = require('fs');
const path = require('path');
const vm = require('vm');

const source = fs.readFileSync(path.join(__dirname, '../static/js/my-housing-strategy.js'), 'utf8');
assert.doesNotMatch(source, /function\s+(phase|statusFor|channelData|effortData|progressDiagnosis)\s*\(/,
  'Business-rule functions must stay out of the browser bundle');
assert.match(source, /\/api\/strategies\/current/, 'Progress sync must request a complete backend strategy');

class Classes {
  constructor() { this.values = new Set(); }
  add(...items) { items.forEach(item => this.values.add(item)); }
  remove(...items) { items.forEach(item => this.values.delete(item)); }
  contains(item) { return this.values.has(item); }
  toggle(item) { if (this.values.delete(item)) return false; this.values.add(item); return true; }
}

let expandButtons = [];
class Element {
  constructor(id, value = '') {
    Object.assign(this, {id, value, textContent: '', style: {}, dataset: {}, classList: new Classes(),
      attributes: {}, disabled: false, _html: ''});
  }
  set innerHTML(value) {
    this._html = String(value);
    if (this.id === 'channelList') {
      expandButtons = [...this._html.matchAll(/data-open="(\d+)"/g)].map(match => {
        const button = new Element(`expand-${match[1]}`);
        const card = {classList: new Classes()};
        button.closest = () => card;
        return button;
      });
    }
  }
  get innerHTML() { return this._html; }
  addEventListener() {}
  setAttribute(name, value) { this.attributes[name] = String(value); }
  getAttribute(name) { return this.attributes[name]; }
  showModal() { this.open = true; }
  close() { this.open = false; }
}

const ids = ['onboarding','strategyForm','identity','city','moveDate','homeType','budget','income',
  'studentReg','universityHousing','areaFlex','loading','loadingTitle','result','regenInfo','editBtn',
  'regenBtn','stateIcon','stateTitle','stateDesc','days','planBCard','planBStage','planBTitle','planBDesc',
  'profileChips','topActions','effortCopy','effortChart','effortLegend','chartTooltip','channelList',
  'progressState','pApplications','pReplies','pViewings','pActive','progressDiagnosis','manageProgressBtn',
  'phaseCopy','phaseTrack','phaseTrigger','explainToggle','explainBody','factorGrid','explainText',
  'editDialog','closeDialog','dialogFormMount','cancelEdit','saveEdit','toast'];
const elements = new Map(ids.map(id => [id, new Element(id)]));

function strategy(viewings) {
  return {
    engine_version: 'strategy-v2-backend-2026-08-26',
    profile: {identity:'master',city:'Den Haag',moveDate:'2027-10-01',homeType:'studio',budget:1050,
      income:'stipend',studentReg:'registered',universityHousing:'waiting',areaFlex:'maybe'},
    progress: {applications:4,replies:viewings ? 2 : 0,viewings,active:3,confirmed:0,tracked:4,mainChannel:'commercial'},
    days: 400,
    phase: {index:0,name:'提前布局',copy:'后端阶段文案',trigger:'后端触发条件',steps:[
      {name:'提前布局',range:'> 90 天'},{name:'主动找房',range:'46–90 天'},
      {name:'扩大覆盖',range:'15–45 天'},{name:'紧急落地',range:'≤ 14 天'}]},
    status: {icon:'◎',title:viewings ? '后端 Viewing 结果' : '后端退回结果',description:'后端说明'},
    plan_b: {tone:'safe',stage:'暂不启动',title:'后端 Plan B',description:'后端 Plan B 说明'},
    profile_chips:['硕士','Den Haag'], top_actions:[{when:'今天',title:'后端行动',tone:'hot'}],
    effort:[{total:30,rows:[{kind:'commercial',name:'综合平台',minutes:30,percent:100,action:'申请',color:'#123456'}]}],
    effort_copy:'后端投入说明',
    channels:[{kind:'commercial',name:'Pararius / Funda',subtitle:'后端渠道',stars:4,state:'当前有效',
      tone:'daily',action:'后端动作',effort:'高',why:'后端依据',adjust:'后端调整',platforms:[
        {name:'Pararius',state:'每日查看',tone:'watch',note:'后端平台说明',label:'打开平台',url:'https://www.pararius.com/'}]}],
    progress_diagnosis:{title:'后端诊断。',text:viewings ? '有 Viewing。' : 'Viewing 已归零。'},
    factors:[{label:'申请反馈',value:`4 / ${viewings} Viewing`}], explanation:'后端完整解释。'
  };
}

elements.get('identity').value = 'master'; elements.get('city').value = 'Leiden';
elements.get('moveDate').value = '2027-09-01'; elements.get('homeType').value = 'room';
elements.get('budget').value = '900'; elements.get('income').value = 'none';
elements.get('studentReg').value = 'unknown'; elements.get('universityHousing').value = 'unknown';
elements.get('areaFlex').value = 'yes';

const document = {
  querySelector(selector) {
    if (selector === 'meta[name="csrf-token"]') return {content:'csrf'};
    return selector.startsWith('#') ? elements.get(selector.slice(1)) || null : null;
  },
  querySelectorAll(selector) { return selector === '.expand-btn' ? expandButtons : []; }
};
const calls = [];
const context = {
  document, URLSearchParams, Math, Number, JSON, Object, console,
  window: {location:{search:''}, scrollTo(){}, EXPATUS_STRATEGY_STATE:{
    latest_profile: strategy(2).profile, strategy: strategy(2), used_today:2, daily_limit:3}},
  fetch: async url => { calls.push(url); return {ok:true,json:async()=>({ok:true,strategy:strategy(0)})}; },
  setTimeout(callback) { callback(); return 1; }, clearTimeout(){}, setInterval(){ return 1; }, clearInterval(){}
};

vm.runInNewContext(source, context, {filename:'my-housing-strategy.js'});
assert.equal(elements.get('city').value, 'Den Haag');
assert.equal(elements.get('stateTitle').textContent, '后端 Viewing 结果');
assert.equal(elements.get('pViewings').textContent, 2);
assert.match(elements.get('channelList').innerHTML, /https:\/\/www\.pararius\.com\//);
assert.doesNotMatch(elements.get('channelList').innerHTML, /href="#"|onclick=/);

Promise.resolve(elements.get('manageProgressBtn').onclick()).then(() => {
  assert.equal(calls.at(-1), '/api/strategies/current');
  assert.equal(elements.get('pViewings').textContent, 0, 'Reverted current state comes from backend');
  assert.equal(elements.get('stateTitle').textContent, '后端退回结果', 'Whole strategy is replaced');
  assert.equal(elements.get('manageProgressBtn').textContent, '同步并重新计算');
  console.log('PASS frontend: renderer-only contract and complete backend recalculation');
}).catch(error => { console.error(error); process.exitCode = 1; });
