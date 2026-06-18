
class Component extends DCLogic {
  state = {
    page:'today', theme:'light', present:false, navOpen:false,
    company:'恒瑞医药', compareCompany:'复星医药', year:2024, scope:'industry', topK:5, demoStep:0,
    deepseek:true, anim:0,
    chatMsgs:null, chatInput:'', chatActive:0, chatLoading:false, chatConvs:null, chatConvId:null, chatSidebar:true, chatSettings:false, chatCtxOn:true, chatModel:'flash',
    cmpTab:'profile',
    resMode:'single', resTopic:'', resList:'恒瑞医药、复星医药、药明康德', resLoading:false, resDone:true, resBatchActive:0, resData:{},
    wbTab:'flow',
    dbTable:'fact_financial', dbSearch:'',
    advLoading:false, advDone:true, advData:null,
    api:{}
  };

  D = {
    companies:['恒瑞医药','复星医药','药明康德','智飞生物','华兰生物','迈瑞医疗','长春高新','云南白药','片仔癀','信达生物','百济神州','华东医药','科伦药业','人福医药','信立泰'],
    industries:['医药生物','化学制药','生物制品','中药','医疗器械','医疗服务'],
    years:[2024,2023,2022,2021,2020],
    stats:{companies:48, documents:312, financial_facts:18642, macro_facts:1286},
    trendYears:['2020','2021','2022','2023','2024'],
    rev:[277.4,259.1,212.8,228.2,279.9],
    np:[63.3,45.3,39.1,43.0,63.4],
    rd:[49.9,62.0,48.9,49.5,65.8],
    gm:[87.9,85.6,83.6,84.9,86.6],
    ranking:[
      {name:'复星医药',value:410.7},{name:'华东医药',value:406.2},{name:'恒瑞医药',value:279.9,sel:true},
      {name:'人福医药',value:244.6},{name:'科伦药业',value:221.6},{name:'信立泰',value:39.5}
    ],
    alerts:[
      {severity:'高',company:'复星医药',year:2024,category:'风险',signal:'商誉减值规模偏高',detail:'商誉账面价值占净资产 18.4%，并购整合后续减值压力需持续关注。'},
      {severity:'中',company:'恒瑞医药',year:2024,category:'财务',signal:'应收账款周转放缓',detail:'应收账款周转天数同比上升 9 天，需关注集采放量下的回款节奏。'},
      {severity:'中',company:'恒瑞医药',year:2024,category:'合规',signal:'研发资本化为零',detail:'研发投入全部费用化，口径稳健但短期压低当期利润弹性。'},
      {severity:'低',company:'华东医药',year:2024,category:'创新',signal:'创新管线集中度高',detail:'核心收入对单一治疗领域依赖度较高，需关注产品迭代风险。'}
    ],
    fosun:{rev:[303.0,390.0,439.0,414.0,410.7],np:[37.0,47.4,37.3,23.9,27.7],rd:[40.0,49.0,52.0,55.8,55.0],gm:[55.0,58.0,53.0,49.0,47.8]},
    /*__DATA__*/
  };

  // ---- helpers ----
  cu(t,dec){ const k=this.state.anim; const v=t*k; if(dec) return v.toFixed(dec); return Math.round(v); }
  nf(n){ return Number(n).toLocaleString('en-US'); }
  yi(){ return this.D.trendYears.indexOf(String(this.state.year)); }

  go(p){ this.setState({page:p, navOpen:false, anim:0}, ()=>{ this.runCount(); this.loadPage(); }); }
  runCount(){
    if(this._raf) cancelAnimationFrame(this._raf);
    if(window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches){ this.setState({anim:1}); return; }
    const t0=performance.now(), dur=820;
    const tick=(t)=>{ let k=Math.min(1,(t-t0)/dur); k=1-Math.pow(1-k,3); this.setState({anim:k}); if(k<1) this._raf=requestAnimationFrame(tick); };
    this._raf=requestAnimationFrame(tick);
  }
  componentDidMount(){ this.runCount(); this.loadBootstrap(); this.loadPage(); this._initConvs(); }

  // ===================== 多会话 / 历史对话 =====================
  _initConvs(){
    let convs=null;
    try{ convs=JSON.parse(window.localStorage.getItem('di_chat_convs')||'null'); }catch(e){}
    if(!Array.isArray(convs)||!convs.length){ convs=[{id:'c'+Date.now(), title:'新对话', msgs:[]}]; }
    this.setState({chatConvs:convs, chatConvId:convs[0].id, chatMsgs:convs[0].msgs||[]});
  }
  _saveConvs(){
    const convs=(this.state.chatConvs||[]).slice();
    const cur=convs.find(c=>c.id===this.state.chatConvId);
    if(cur){ cur.msgs=this.state.chatMsgs||[]; const fu=(cur.msgs.find(m=>m.role==='user')||{}).text; if(fu) cur.title=fu.slice(0,18); }
    this.setState({chatConvs:convs});
    try{ window.localStorage.setItem('di_chat_convs', JSON.stringify(convs.slice(0,30))); }catch(e){}
  }
  newChat(){
    const convs=(this.state.chatConvs||[]).slice();
    const cur=convs.find(c=>c.id===this.state.chatConvId); if(cur) cur.msgs=this.state.chatMsgs||[];
    const nc={id:'c'+Date.now(), title:'新对话', msgs:[]}; convs.unshift(nc);
    this.setState({chatConvs:convs, chatConvId:nc.id, chatMsgs:[], chatActive:0, chatInput:''}, ()=>this._saveConvs());
  }
  switchChat(id){
    if(id===this.state.chatConvId) return;
    const convs=(this.state.chatConvs||[]).slice();
    const cur=convs.find(c=>c.id===this.state.chatConvId); if(cur) cur.msgs=this.state.chatMsgs||[];
    const tg=convs.find(c=>c.id===id); if(!tg) return;
    let ai=0; for(let i=(tg.msgs||[]).length-1;i>=0;i--){ if(tg.msgs[i].role==='ai'){ ai=i; break; } }
    this.setState({chatConvs:convs, chatConvId:id, chatMsgs:tg.msgs||[], chatActive:ai}, ()=>this._saveConvs());
  }
  _respText(resp){ if(!resp) return ''; if(resp.mdText) return resp.mdText; return (resp.blocks||[]).map(b=>b.text).join('\n'); }
  _persist(){ try{ window.localStorage.setItem('di_chat_convs', JSON.stringify((this.state.chatConvs||[]).slice(0,30))); }catch(e){} }
  deleteChat(id){
    let convs=(this.state.chatConvs||[]).slice();
    const cur=convs.find(c=>c.id===this.state.chatConvId); if(cur) cur.msgs=this.state.chatMsgs||[];
    convs=convs.filter(c=>c.id!==id);
    let cid=this.state.chatConvId, msgs=this.state.chatMsgs;
    if(id===cid){
      if(!convs.length){ const nc={id:'c'+Date.now(),title:'新对话',msgs:[]}; convs=[nc]; cid=nc.id; msgs=[]; }
      else { cid=convs[0].id; msgs=convs[0].msgs||[]; }
    }
    this.setState({chatConvs:convs, chatConvId:cid, chatMsgs:msgs, chatActive:0}, ()=>this._persist());
  }
  clearAllChats(){
    const nc={id:'c'+Date.now(),title:'新对话',msgs:[]};
    this.setState({chatConvs:[nc], chatConvId:nc.id, chatMsgs:[], chatActive:0, chatSettings:false}, ()=>this._persist());
  }

  // ===================== Backend (/api) data layer =====================
  _api(path, params){
    const url = new URL(path, window.location.origin);
    if(params){ Object.keys(params).forEach(k=>{ const v=params[k]; if(v!=null&&v!=='') url.searchParams.set(k, v); }); }
    return fetch(url.toString(), {headers:{'accept':'application/json'}}).then(r=>{ if(!r.ok) throw new Error('GET '+path+' → '+r.status); return r.json(); });
  }
  _apiPost(path, body){
    return fetch(path, {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(body)}).then(r=>{ if(!r.ok) throw new Error('POST '+path+' → '+r.status); return r.json(); });
  }
  _mergeApi(patch){ this.setState(st=>({api:Object.assign({}, st.api, patch)})); }
  _curKey(){ const s=this.state; return [s.company,s.year,s.scope].join('|'); }
  _get(key){ const a=this.state.api||{}; return a[key]; }
  // stale-while-revalidate：返回该槽位最近一次成功拉取的数据（即便正在切换/key 不匹配），
  // 避免切公司时回退到演示预设造成闪烁；新数据到达后会覆盖该槽位自动更新。
  _matched(slot){ const m=this._get(slot); return m ? m.data : null; }

  loadBootstrap(){
    this._api('/api/bootstrap').then(b=>{
      if(!b) return;
      const ns={}; let nav=false;
      if(typeof b.deepseek_enabled==='boolean') ns.deepseek=b.deepseek_enabled;
      const comps=(Array.isArray(b.companies)?b.companies:[]).filter(c=>String(c).indexOf('模拟')<0);
      const yrs=Array.isArray(b.years)?b.years:[];
      if(comps.length && comps.indexOf(this.state.company)<0){ ns.company=comps[0]; nav=true; }
      const baseCompany=ns.company||this.state.company;
      if(comps.length>1){ const cc=this.state.compareCompany; if(!cc || comps.indexOf(cc)<0 || cc===baseCompany){ ns.compareCompany=comps.find(c=>c!==baseCompany)||''; } }
      if(yrs.length && yrs.indexOf(this.state.year)<0){ ns.year=Number(yrs[0]); nav=true; }
      this.setState(Object.assign({api:Object.assign({}, this.state.api, {bootstrap:b})}, ns), ()=>{ if(nav) this.runCount(); this.loadPage(); });
    }).catch(()=>{});
  }

  loadPage(){
    const p=this.state.page;
    if(p==='today') this.loadDashboard();
    else if(p==='compare'){ this.loadProfile(); this.loadCompare(); }
    else if(p==='timeline') this.loadTimeline();
    else if(p==='database') this.loadDbCatalog();
    else if(p==='whitebox') this.loadWhitebox();
    else if(p==='advanced') this.loadProfile();
    else if(p==='research') this._ensureResProfile(this._resActive());
  }

  loadDashboard(){ const key=this._curKey(), s=this.state;
    this._api('/api/dashboard',{company_name:s.company, report_year:s.year, ranking_scope:s.scope}).then(d=>this._mergeApi({dashboard:{key,data:d}})).catch(()=>{}); }
  loadProfile(){ const key=this._curKey(), s=this.state;
    this._api('/api/profile',{company_name:s.company, report_year:s.year}).then(d=>this._mergeApi({profile:{key,data:d}})).catch(()=>{}); }
  loadCompare(){ const key=this._curKey(), s=this.state;
    this._api('/api/compare',{company_name:s.company, compare_company_name:s.compareCompany, report_year:s.year}).then(d=>this._mergeApi({compare:{key,data:d}})).catch(()=>{}); }
  loadTimeline(){ const key=this.state.company;
    this._api('/api/timeline',{company_name:this.state.company}).then(d=>this._mergeApi({timeline:{key,data:d}})).catch(()=>{}); }
  loadWhitebox(){ if(this._get('whitebox')) return; this._api('/api/whitebox').then(d=>this._mergeApi({whitebox:d})).catch(()=>{}); }
  loadDbCatalog(){
    this._api('/api/database/catalog').then(d=>{
      this._mergeApi({dbCatalog:d});
      const names=(d&&d.table_names)||[];
      let t=this.state.dbTable;
      if(names.length && names.indexOf(t)<0){ t=names[0]; this.setState({dbTable:t}); }
      this.loadDbTable(t);
    }).catch(()=>{});
  }
  loadDbTable(name){ if(!name) return; const cur=this._get('dbTable');
    if(cur && cur.key===name) return;
    this._api('/api/database/table',{table_name:name, limit:20}).then(d=>this._mergeApi({dbTable:{key:name,data:d}})).catch(()=>{}); }
  selectDbTable(name){ this.setState({dbTable:name}, ()=>this.loadDbTable(name)); }

  setParam(patch){ this.setState(Object.assign({anim:0}, patch), ()=>{ this.runCount(); this.loadPage(); }); }

  // ---- adapters: backend (snake_case) shapes -> design shapes ----
  _num(v){ const n=Number(v); return isFinite(n)?n:null; }
  // 金额量级格式化：后端金额以「元」返回，前端按 亿元/万元 展示；比率(%)与已是亿元/万元的不动。
  _amtParts(v, unit){ v=this._num(v); const u=unit||''; if(v==null) return {num:0, unit:u};
    const isPct=u.indexOf('%')>=0;
    if(isPct && Math.abs(v)<1e5) return {num:v, unit:'%'};   // 正常比率
    // '元'/空单位，或被误标成 %、却是极大金额(>=1e5)的数据异常 → 按金额折算
    if(u===''||u==='元'||isPct){ const a=Math.abs(v); if(a>=1e8) return {num:v/1e8, unit:'亿元'}; if(a>=1e4) return {num:v/1e4, unit:'万元'}; return {num:v, unit:'元'}; }
    return {num:v, unit:u}; }
  _amt(v, unit){ const p=this._amtParts(v, unit); return Number(p.num).toFixed(2)+p.unit; }
  _fmtAmtStr(s){ if(s==null) return '-'; s=String(s); const m=s.match(/^\s*(-?[\d,]*\.?\d+)\s*(.*)$/); if(!m) return s; if(/亿|万/.test(m[2]||'')) return s; const num=parseFloat(m[1].replace(/,/g,'')); if(!isFinite(num)) return s; return this._amt(num, m[2]||''); }
  _stripMd(s){ return String(s==null?'':s).replace(/\*\*(.*?)\*\*/g,'$1').replace(/\*(.*?)\*/g,'$1').replace(/`([^`]*)`/g,'$1').replace(/^>\s?/,'').trim(); }
  _mdBlocks(md){
    const lines=String(md||'').split(/\r?\n/);
    const out=[];
    const isRow=(l)=>/^\s*\|.*\|\s*$/.test(l);
    const isSep=(l)=>/^\s*\|[\s:|\-—]+\|\s*$/.test(l) && /[-—]/.test(l);
    const cells=(l)=>l.trim().replace(/^\|/,'').replace(/\|$/,'').split('|').map(c=>this._stripMd(c.trim()));
    for(let i=0;i<lines.length;i++){
      const raw=lines[i], t=raw.trim();
      if(!t) continue;
      if(isRow(raw)){
        const block=[]; let j=i;
        while(j<lines.length && isRow(lines[j])){ block.push(lines[j]); j++; }
        i=j-1;
        block.filter(l=>!isSep(l)).forEach((l,idx)=>{
          const c=cells(l).filter(x=>x!=='');
          if(c.length) out.push({t: idx===0?'p':'li', text:c.join(' · ')});
        });
        continue;
      }
      let m;
      if(m=t.match(/^#{1,6}\s+(.*)$/)) out.push({t:'h2', text:this._stripMd(m[1])});
      else if(/^[-—*_]{3,}$/.test(t)) continue; // 跳过 --- 分割线
      else if(m=t.match(/^([-*•])\s+(.*)$/)) out.push({t:'li', text:this._stripMd(m[2])});
      else if(m=t.match(/^\d+[\.、\)]\s+(.*)$/)) out.push({t:'li', text:this._stripMd(m[1])});
      else out.push({t:'p', text:this._stripMd(t)});
    }
    return out.length?out:[{t:'p', text:this._stripMd(md)}];
  }
  _chunkAdapt(chunks, scoreAsString){ return (Array.isArray(chunks)?chunks:[]).map((c,i)=>{ const meta=c.metadata||{}; const dist=this._num(c.distance);
      let sc = (this._num(c.score)!=null)? this._num(c.score) : (dist!=null? Math.max(0.4, 1-dist) : (0.92-i*0.04));
      sc=Math.max(0,Math.min(1,sc));
      const source=meta.source||c.source||('来源 '+(i+1));
      const doc_id=(meta.page!=null?('第 '+meta.page+' 页'):(meta.doc_type||c.doc_id||''));
      return {source, score: scoreAsString? sc.toFixed(3): sc, doc_id, text:c.text||''}; }); }
  _sqlTable(rows){ rows=Array.isArray(rows)?rows:[]; if(!rows.length) return {cols:[], rows:[]};
    const cols=Object.keys(rows[0]); return {cols, rows:rows.slice(0,12).map(r=>cols.map(c=>{ const v=r[c]; return v==null?'-':String(v); }))}; }
  _pivot(spec){ if(!spec||!Array.isArray(spec.rows)||!spec.rows.length) return null;
    const xk=spec.x||'report_year', yk=spec.y||'value_num', sk=spec.series||'indicator_name';
    const xs=[]; const map={};
    spec.rows.forEach(r=>{ const xv=String(r[xk]); if(xs.indexOf(xv)<0) xs.push(xv); const sn=String(r[sk]); (map[sn]=map[sn]||{})[xv]=this._num(r[yk]); });
    xs.sort((a,b)=>{ const na=parseFloat(a), nb=parseFloat(b); if(!isNaN(na)&&!isNaN(nb)) return na-nb; return a<b?-1:(a>b?1:0); });
    const palette=['#3b428f','#0d9488','#b45309','#6d28d9','#0ea5e9','#db2777'];
    const names=Object.keys(map);
    return {labels:xs, series:names.map((nm,i)=>({name:nm, color:palette[i%palette.length], values:xs.map(x=> map[nm][x]!=null?map[nm][x]:null)}))}; }
  _seriesValues(pivot, name){ if(!pivot||!pivot.series.length) return null; const s=pivot.series.find(x=>x.name===name); return s?s.values:null; }
  _liveCompanies(){ const b=this._get('bootstrap'); const list=(b&&Array.isArray(b.companies)&&b.companies.length)?b.companies:this.D.companies; const src=list.filter(c=>String(c).indexOf('模拟')<0); const base=src.length?src:list; const seen={}, out=[]; base.forEach(c=>{ const k=String(c).trim(); if(k&&!seen[k]){ seen[k]=1; out.push(c); } }); return out; }
  _liveYears(){ const b=this._get('bootstrap'); return (b&&Array.isArray(b.years)&&b.years.length)?b.years:this.D.years; }
  // 研报页：当前激活公司（单条=全局公司；批量=当前选中的批量公司）
  _resActive(){ const s=this.state; if(s.resMode==='batch'){ const names=(s.resList||'').split(/[，,、\n]+/).map(x=>x.trim()).filter(Boolean).slice(0,5); return names[s.resBatchActive]||names[0]||s.company; } return s.company; }
  // 按需拉取某公司的画像供研报页用（按 name|year 缓存去重，可安全在 render 中调用）
  _ensureResProfile(name){ if(!name) return; const y=this.state.year, key=name+'|'+y;
    const cache=(this.state.api&&this.state.api.resProfile)||{}; if(cache[key]) return;
    this._resInflight=this._resInflight||{}; if(this._resInflight[key]) return; this._resInflight[key]=1;
    this._api('/api/profile',{company_name:name, report_year:y}).then(d=>{ delete this._resInflight[key]; if(d&&d.company_name) this._lastResProf=d; this.setState(st=>({api:Object.assign({},st.api,{resProfile:Object.assign({},(st.api&&st.api.resProfile)||{},{[key]:d})})})); }).catch(()=>{ delete this._resInflight[key]; }); }
  // 当前公司画像；未就绪时退回上一份已加载的真实画像(stale)，避免闪演示数据
  _resProfile(name){ const c=((this.state.api&&this.state.api.resProfile)||{})[name+'|'+this.state.year]; return (c&&c.company_name)?c:(this._lastResProf||c); }

  navDef(){
    return {
      main:[
        {key:'today',label:'工作台',icon:['M3 3h7v7H3zM14 3h7v7h-7zM14 14h7v7h-7zM3 14h7v7H3z']},
        {key:'chat',label:'智能问答',icon:['M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z']},
        {key:'compare',label:'公司画像 · 对比',icon:['M4 4h6v16H4zM14 4h6v16h-6z']},
        {key:'research',label:'自动化研报',icon:['M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z','M14 2v6h6','M9 13h6','M9 17h6']},
        {key:'whitebox',label:'白盒溯源',icon:['M3 7V5a2 2 0 0 1 2-2h2','M17 3h2a2 2 0 0 1 2 2v2','M21 17v2a2 2 0 0 1-2 2h-2','M7 21H5a2 2 0 0 1-2-2v-2','M7 12h10'],badge:'核心'}
      ],
      analysis:[
        {key:'database',label:'数据库浏览',icon:['M12 3c4.97 0 9 1.34 9 3s-4.03 3-9 3-9-1.34-9-3 4.03-3 9-3','M3 6v12c0 1.66 4.03 3 9 3s9-1.34 9-3V6','M3 12c0 1.66 4.03 3 9 3s9-1.34 9-3']},
        {key:'timeline',label:'事件时间轴',icon:['M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18z','M12 8v4l3 2']},
        {key:'advanced',label:'高级分析',icon:['M18 8a3 3 0 1 0 0-6 3 3 0 0 0 0 6zM6 15a3 3 0 1 0 0-6 3 3 0 0 0 0 6zM18 21a3 3 0 1 0 0-6 3 3 0 0 0 0 6z','M8.6 13.5l6.8 4M15.4 6.5l-6.8 4']}
      ]
    };
  }
  navItem(it){
    const active = this.state.page===it.key;
    const style='display:flex;align-items:center;gap:11px;padding:0 11px;height:36px;border-radius:9px;font-size:13px;font-weight:500;cursor:pointer;width:100%;text-align:left;border:0;transition:background .12s,color .12s;'+(active?'background:var(--brand-50);color:var(--brand-600);font-weight:600;':'background:transparent;color:var(--text-2);');
    return Object.assign({}, it, {style, onClick:()=>this.go(it.key)});
  }

  shellVals(){
    const s=this.state;
    const nd=this.navDef();
    const META={today:['工作台','今日总览'],chat:['智能问答','对话与证据'],compare:['公司画像','双公司对比'],research:['自动化研报','报告生成'],whitebox:['白盒溯源','可解释链路'],database:['数据底座','数据库浏览'],timeline:['事件时间轴','公司动态'],advanced:['高级分析','图谱与编排']};
    const m=META[s.page]||['',''];
    const segBase='flex:1;height:24px;border:0;border-radius:5px;font-size:11.5px;font-weight:500;cursor:pointer;transition:all .12s;';
    return {
      theme:s.theme, present:s.present?'on':'off', navOpenAttr:s.navOpen?'1':'0',
      navMain:nd.main.map(it=>this.navItem(it)), navAnalysis:nd.analysis.map(it=>this.navItem(it)),
      crumbGroup:m[0], crumbSub:m[1],
      company:s.company, year:s.year, topK:s.topK, companies:this._liveCompanies(), years:this._liveYears(),
      isToday:s.page==='today', isChat:s.page==='chat', isCompare:s.page==='compare', isResearch:s.page==='research', isWhitebox:s.page==='whitebox', isDatabase:s.page==='database', isTimeline:s.page==='timeline', isAdvanced:s.page==='advanced',
      themeIcon: s.theme==='dark'?['M12 3a6 6 0 0 0 9 9 9 9 0 1 1-9-9z']:['M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M6.3 17.7l-1.4 1.4M19.1 4.9l-1.4 1.4','M12 8a4 4 0 1 0 0 8 4 4 0 0 0 0-8z'],
      toggleTheme:()=>this.setState({theme:s.theme==='dark'?'light':'dark'}),
      togglePresent:()=>this.setState({present:!s.present}),
      toggleMode:()=>this.setState({deepseek:!s.deepseek}),
      openNav:()=>this.setState({navOpen:true}), closeNav:()=>this.setState({navOpen:false}),
      onCompany:(e)=>this.setParam({company:e.target.value}),
      onYear:(e)=>this.setParam({year:Number(e.target.value)}),
      onScopeInd:()=>this.setParam({scope:'industry'}), onScopeAll:()=>this.setParam({scope:'all'}),
      onTopK:(e)=>this.setState({topK:Number(e.target.value)}),
      scopeIndStyle:segBase+(s.scope==='industry'?'background:var(--brand-600);color:#fff;':'background:transparent;color:var(--text-2);'),
      scopeAllStyle:segBase+(s.scope==='all'?'background:var(--brand-600);color:#fff;':'background:transparent;color:var(--text-2);'),
      statusColor:s.deepseek?'var(--pos)':'var(--warn)',
      statusText:s.deepseek?'DeepSeek 增强已启用':'本地降级模式 · 离线可跑',
      modeLabel:s.deepseek?'增强模式':'本地模式',
      modeColor:s.deepseek?'var(--pos)':'var(--warn)',
      modeBg:s.deepseek?'var(--pos-bg)':'var(--warn-bg)',
      modeBorder:'transparent',
      presentColor:s.present?'#fff':'var(--text-2)', presentBg:s.present?'var(--brand-600)':'var(--bg-elev)', presentBorder:s.present?'var(--brand-600)':'var(--border)',
      goChat:()=>this.go('chat'), goResearch:()=>this.go('research'), goCompare:()=>this.go('compare'), goWhitebox:()=>this.go('whitebox'),
      presentOn:s.present, demoIdx:s.demoStep+1, demoTotal:5,
      demoPrev:()=>this.demoGo(s.demoStep-1), demoNext:()=>this.demoGo(s.demoStep+1),
      demoSteps:this.demoStepsDef().map((d,i)=>({t:d.t,idx:i+1,onClick:()=>this.demoGo(i),
        style:'display:inline-flex;align-items:center;gap:6px;font-size:12px;font-weight:500;border:0;cursor:pointer;border-radius:999px;padding:6px 13px;transition:all .12s;'+(i===s.demoStep?'background:#fff;color:var(--brand-800)':'background:rgba(255,255,255,.1);color:rgba(255,255,255,.82)')}))
    };
  }

  todayVals(){
    const D=this.D, s=this.state, yi=this.yi()<0?4:this.yi();
    const ic={biz:['M3 21h18M5 21V7l8-4v18M19 21V11l-6-4'],doc:['M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z','M14 2v6h6'],fact:['M3 3v18h18','M7 16l4-5 3 3 4-6'],macro:['M22 12h-4l-3 9L9 3l-3 9H2']};
    const boot=this._get('bootstrap'); const stats=(boot&&boot.stats)||D.stats;
    const _yrs=this._liveYears(); const yrHint=(_yrs&&_yrs.length)?(Math.min.apply(null,_yrs)+'–'+Math.max.apply(null,_yrs)+' 全量入库'):'年报全量入库';
    const today_kpis=[
      {label:'覆盖企业',value:this.cu(stats.companies),hint:'医药生物多细分赛道',icon:ic.biz},
      {label:'年报文档',value:this.cu(stats.documents),hint:yrHint,icon:ic.doc},
      {label:'财务事实',value:this.nf(this.cu(stats.financial_facts)),hint:'结构化指标条目',icon:ic.fact},
      {label:'宏观指标',value:this.nf(this.cu(stats.macro_facts)),hint:'卫生类联动数据',icon:ic.macro}
    ];
    const sc=(k)=>()=>this.go(k);
    const today_scenes=[
      {title:'智能问答',desc:'自然语言提问，自动路由 SQL / RAG / 宏观，回答附带可追溯证据。',cta:'去提问',onClick:sc('chat'),tint:'var(--series-1)',tintBg:'var(--brand-50)',icon:['M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z']},
      {title:'深度研究',desc:'一键编排「检索→抽取→合成→校验」，产出可下载的 Markdown 研报。',cta:'生成研报',onClick:sc('research'),tint:'var(--series-2)',tintBg:'rgba(13,148,136,.1)',icon:['M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z','M14 2v6h6','M9 13h6','M9 17h6']},
      {title:'公司画像 · 对比',desc:'单家全景画像，或与同业对手做多指标横向对比与可视化。',cta:'看对比',onClick:sc('compare'),tint:'var(--series-4)',tintBg:'rgba(109,40,217,.1)',icon:['M4 4h6v16H4zM14 4h6v16h-6z']},
      {title:'白盒溯源',desc:'公开 SQL、RAG 原文切片与推理链路，每个结论都能回看来路。',cta:'看链路',onClick:sc('whitebox'),tint:'var(--series-3)',tintBg:'rgba(180,83,9,.1)',icon:['M3 7V5a2 2 0 0 1 2-2h2','M17 3h2a2 2 0 0 1 2 2v2','M21 17v2a2 2 0 0 1-2 2h-2','M7 21H5a2 2 0 0 1-2-2v-2','M7 12h10']}
    ];
    const dash=this._matched('dashboard');
    // ----- 同业排名（live: dashboard.ranking_overview.boards[0]） -----
    const ro=dash&&dash.ranking_overview;
    const board=ro&&Array.isArray(ro.boards)&&ro.boards.length?ro.boards[0]:null;
    let today_ranking, today_rankN, today_industry, today_rankScope;
    if(board && Array.isArray(board.rows) && board.rows.length){
      const mx=Math.max.apply(null, board.rows.map(r=>this._num(r.value_num)||0))||1;
      today_ranking=board.rows.map((r,i)=>{ const val=this._num(r.value_num)||0; const sel=!!r.is_selected; return {rank:r.rank||(i+1),name:r.company_name,value:this._amt(val, r.unit||board.unit||'元'),pct:(val/mx*100).toFixed(0),sel,weight:sel?'600':'500',nameColor:sel?'var(--brand-600)':'var(--text)',barColor:sel?'var(--brand-600)':'var(--gray-300)'}; });
      today_rankN=board.sample_size||today_ranking.length;
      today_industry=(ro&&ro.industry_name)||'化学制药';
      today_rankScope=(ro&&ro.scope_label)||(s.scope==='industry'?'同一级行业排名':'全行业排名');
    } else {
      const mx=Math.max.apply(null,D.ranking.map(r=>r.value));
      today_ranking=D.ranking.map((r,i)=>({rank:i+1,name:r.name,value:r.value.toFixed(1),pct:(r.value/mx*100).toFixed(0),sel:!!r.sel,
        weight:r.sel?'600':'500',nameColor:r.sel?'var(--brand-600)':'var(--text)',barColor:r.sel?'var(--brand-600)':'var(--gray-300)'}));
      today_rankN=18; today_industry='化学制药'; today_rankScope=s.scope==='industry'?'同一级行业排名':'全行业排名';
    }
    // ----- 预警中心（live: dashboard.alert_overview.items） -----
    const sev={'高':{c:'var(--neg)',b:'var(--neg-bg)'},'中':{c:'var(--warn)',b:'var(--warn-bg)'},'低':{c:'var(--info)',b:'var(--info-bg)'}};
    const ao=dash&&dash.alert_overview;
    let today_alerts, today_alertSummary;
    if(ao && Array.isArray(ao.items) && ao.items.length){
      today_alerts=ao.items.slice(0,8).map(a=>{ const sv=sev[a.severity]||sev['低']; return {severity:a.severity,company:a.company_name,year:a.report_year,signal:a.signal,detail:a.detail,sevColor:sv.c,sevBg:sv.b}; });
      const high=ao.items.filter(x=>x.severity==='高').length;
      const cover=new Set(ao.items.map(x=>x.company_name)).size;
      today_alertSummary='共 '+ao.items.length+' 条信号 · 高优先级 '+high+' · 覆盖 '+cover+' 家';
    } else {
      today_alerts=D.alerts.map(a=>({severity:a.severity,company:a.company,year:a.year,signal:a.signal,detail:a.detail,sevColor:sev[a.severity].c,sevBg:sev[a.severity].b}));
      today_alertSummary='共 16 条信号 · 高优先级 3 · 覆盖 9 家';
    }
    // ----- 关键指标 + 营收趋势（live: dashboard.trend_overview） -----
    const to=dash&&dash.trend_overview;
    const statusColor=(lvl)=>({green:'var(--pos)',amber:'var(--neg)',red:'var(--neg)',neutral:'var(--text-3)'})[lvl]||'var(--pos)';
    const shortLabel=(l)=>({'归属于上市公司股东的净利润':'归母净利润','经营活动产生的现金流量净额':'经营现金流'})[l]||l;
    let today_metrics, today_trendLabels, today_trendSeries;
    if(to && Array.isArray(to.cards) && to.cards.length){
      today_metrics=to.cards.slice(0,4).map(c=>{ const sp=this._amtParts(c.value, c.unit); return {label:shortLabel(c.label),value:this.cu(sp.num,2),unit:sp.unit,delta:c.change_text||'—',deltaColor:statusColor(c.status&&c.status.level)}; });
      const piv=this._pivot(to.amount_chart);
      if(piv){ today_trendLabels=piv.labels; const rev=this._seriesValues(piv,'营业收入'); today_trendSeries=[{name:'营业收入',color:'#3b428f',values:rev||piv.series[0].values}]; }
    }
    if(!today_metrics){
      const dgn=(arr)=>{ const cur=arr[yi], prev=arr[yi-1]; if(prev==null) return {t:'—',pos:true}; const d=(cur-prev)/Math.abs(prev)*100; return {t:(d>=0?'+':'')+d.toFixed(1)+'%',pos:d>=0}; };
      const mk=(label,arr,unit,pct)=>{ const g=pct?{t:(arr[yi]-arr[yi-1]>=0?'+':'')+(arr[yi]-arr[yi-1]).toFixed(1)+'pct',pos:arr[yi]-arr[yi-1]>=0}:dgn(arr); return {label,value:this.cu(arr[yi],1),unit,delta:g.t,deltaColor:g.pos?'var(--pos)':'var(--neg)'}; };
      today_metrics=[ mk('营业收入',D.rev,'亿元'), mk('归母净利润',D.np,'亿元'), mk('研发投入',D.rd,'亿元'), mk('销售毛利率',D.gm,'%',true) ];
    }
    if(!today_trendLabels){ today_trendLabels=D.trendYears; today_trendSeries=[{name:'营业收入',color:'#3b428f',values:D.rev}]; }
    return {
      today_kpis, today_scenes, today_ranking, today_alerts, today_metrics,
      today_industry, today_rankScope, today_rankN,
      today_alertSummary,
      today_trendLabels, today_trendSeries
    };
  }

  // ---- chat ----
  getMsgs(){ return this.state.chatMsgs || this.seedChat(); }
  // 空开场（避免写死某家公司的演示问答）；首次提问/点推荐问题即走真实 /api/chat
  seedChat(){ return []; }
  _liveChatResp(d){
    const hasSql = Array.isArray(d.sql_rows) && d.sql_rows.length;
    const useMacro = !hasSql && Array.isArray(d.macro_rows) && d.macro_rows.length;
    const tbl=this._sqlTable(useMacro ? d.macro_rows : d.sql_rows);
    return {
      route: d.route?('路由 · '+d.route):'SQL + RAG 混合',
      blocks: this._mdBlocks(d.answer_markdown),
      mdText: d.answer_markdown||'',
      sql: useMacro ? (d.macro_sql||'') : (d.sql||d.macro_sql||''),
      cols: tbl.cols,
      rows: tbl.rows,
      chunks: this._chunkAdapt(d.chunks, false)
    };
  }
  ask(q){
    const prior=this.getMsgs();
    const history=(this.state.chatCtxOn!==false)?prior.filter(m=>(m.role==='user')||(m.role==='ai'&&m.resp)).slice(-8).map(m=>({role:m.role==='user'?'user':'assistant', content:m.role==='user'?(m.text||''):this._respText(m.resp)})):[];
    const msgs=prior.slice();
    msgs.push({role:'user',text:q});
    const ai=msgs.length;
    msgs.push({role:'ai',loading:true,resp:null});
    this.setState({chatMsgs:msgs,chatInput:'',chatActive:ai,chatLoading:true});
    const s=this.state;
    const finish=(resp)=>{ const m2=this.getMsgs().slice(); m2[ai]={role:'ai',loading:false,resp}; this.setState({chatMsgs:m2,chatLoading:false}, ()=>this._saveConvs()); };
    this._apiPost('/api/chat',{question:q, company_name:s.company||null, report_year:s.year||null, top_k:s.topK||5, history, model:s.chatModel||'flash'})
      .then(d=>finish(this._liveChatResp(d)))
      .catch((e)=>{ finish({route:'连接失败', blocks:[{t:'p', text:'⚠️ 在线问答暂时不可用：服务器调用大模型失败（'+String((e&&e.message)||e).slice(0,90)+'）。常见原因是服务器无法连接 api.deepseek.com（DNS/网络）。修复后重试即可。'}], sql:'', cols:[], rows:[], chunks:[]}); });
  }
  send(){ const q=(this.state.chatInput||'').trim(); if(q&&!this.state.chatLoading) this.ask(q); }
  answerFor(q){
    return {
      route:'SQL + RAG 混合',
      blocks:[
        {t:'p',text:'恒瑞医药 2024 年经营质量整体回升，呈现「收入重回增长、盈利弹性释放、研发持续高投入」的特征：'},
        {t:'li',text:'营业收入 279.9 亿元，同比 +22.6%，重回历史高位；集采影响逐步消化，创新药放量贡献主要增量。'},
        {t:'li',text:'归母净利润 63.4 亿元，同比 +47.5%，利润弹性显著高于收入，销售毛利率回升至 86.6%。'},
        {t:'li',text:'研发投入 65.8 亿元（全部费用化），研发强度约 23.5%，在研管线 78 项，创新驱动特征明确。'},
        {t:'p',text:'风险关注：应收账款周转天数同比上升约 9 天，需跟踪集采放量下的回款节奏。'}
      ],
      sql:"SELECT indicator_name, report_year, value_num, unit\nFROM fact_financial\nWHERE company_name = '恒瑞医药'\n  AND report_year IN (2023, 2024)\n  AND indicator_name IN ('营业收入','归母净利润','研发投入','销售毛利率')\nORDER BY indicator_name, report_year;",
      cols:['指标','2023','2024','同比'],
      rows:[['营业收入(亿元)','228.2','279.9','+22.6%'],['归母净利润(亿元)','43.0','63.4','+47.5%'],['研发投入(亿元)','49.5','65.8','+32.9%'],['销售毛利率(%)','84.9','86.6','+1.7pct']],
      chunks:[
        {source:'恒瑞医药 · 2024年年度报告',score:0.912,doc_id:'HRYY-2024-MD-0042',text:'报告期内公司实现营业收入279.91亿元，同比增长22.63%；归属于上市公司股东的净利润63.37亿元，同比增长47.54%……'},
        {source:'恒瑞医药 · 2024年年度报告',score:0.864,doc_id:'HRYY-2024-MD-0118',text:'公司持续加大研发投入，全年研发费用65.83亿元，创新药收入占比进一步提升，多个创新药获批上市……'},
        {source:'恒瑞医药 · 2024年年度报告',score:0.791,doc_id:'HRYY-2024-MD-0203',text:'公司综合毛利率为86.61%，盈利能力保持稳健，销售费用率同比下降，期间费用结构持续优化……'}
      ]
    };
  }
  componentDidUpdate(){ if(this.state.page==='chat'&&this._chatScroll){ this._chatScroll.scrollTop=this._chatScroll.scrollHeight; } }

  // ---- compare / profile ----
  getProf(name){
    const D=this.D;
    const base={
      '恒瑞医药':{track:'化学制药',risk:12,patent:1840,nodes:47,rev:D.rev,np:D.np,rd:D.rd,gm:D.gm,
        metrics:[['营业收入','279.9 亿元','同比 +22.6%'],['归母净利润','63.4 亿元','同比 +47.5%'],['研发投入','65.8 亿元','研发强度 23.5%'],['销售毛利率','86.6 %','同比 +1.7pct'],['经营性现金流','51.2 亿元','同比 +18.3%'],['总资产','558.7 亿元','同比 +9.1%']],
        riskCards:[['高风险信号','1'],['中风险信号','3'],['涉诉事件','4'],['监管问询','0']],
        innovCards:[['发明专利','1,240'],['在研管线','78'],['创新药收入占比','61%'],['研发人员','5,400+']],
        equityCards:[['图谱节点','47'],['关系边','86'],['一级股东','12']],
        patents:{inv:[180,210,245,268,290],uti:[90,105,120,128,140]},
        summary:'恒瑞医药 2024 年收入与利润同步回升，创新药放量驱动盈利弹性，研发强度维持高位，整体经营质量稳健。'},
      '复星医药':{track:'化学制药',risk:23,patent:1260,nodes:63,rev:D.fosun.rev,np:D.fosun.np,rd:D.fosun.rd,gm:D.fosun.gm,
        metrics:[['营业收入','410.7 亿元','同比 -0.8%'],['归母净利润','27.7 亿元','同比 +15.9%'],['研发投入','55.0 亿元','研发强度 13.4%'],['销售毛利率','47.8 %','同比 -1.2pct'],['经营性现金流','38.4 亿元','同比 +6.2%'],['总资产','1,182 亿元','同比 +3.4%']],
        riskCards:[['高风险信号','3'],['中风险信号','6'],['涉诉事件','9'],['监管问询','1']],
        innovCards:[['发明专利','860'],['在研管线','64'],['创新药收入占比','38%'],['研发人员','4,100+']],
        equityCards:[['图谱节点','63'],['关系边','118'],['一级股东','18']],
        patents:{inv:[150,165,178,190,196],uti:[80,88,95,100,104]},
        summary:'复星医药营收体量领先，但毛利率偏低、商誉与涉诉风险更高，盈利质量与风险敞口与恒瑞形成鲜明对照。'}
    };
    const demo=base[name]||base['恒瑞医药'];
    if(name===this.state.company){ const p=this._matched('profile'); if(p && p.company_name){ const live=this._profToProf(p); if(live) return live; } }
    return demo;
  }
  _profToProf(p){
    const cardVal=(label)=>{ const c=(p.cards||[]).find(x=>x.label===label); return c?c.value:undefined; };
    const trend=this._pivot(p.trend_chart), ratio=this._pivot(p.ratio_chart), inno=this._pivot(p.innovation_chart);
    const trendSeries=[];
    const rev=trend?this._seriesValues(trend,'营业收入'):null;
    const np=trend?this._seriesValues(trend,'归属于上市公司股东的净利润'):null;
    const rd=trend?this._seriesValues(trend,'研发费用'):null;
    if(rev) trendSeries.push({name:'营业收入',color:'#3b428f',values:rev});
    if(np) trendSeries.push({name:'归母净利润',color:'#0d9488',values:np});
    if(rd) trendSeries.push({name:'研发投入',color:'#b45309',values:rd});
    const gmSeries = ratio? ratio.series.map(s=>({name:s.name,color:'#6d28d9',values:s.values})) : null;
    let patLabels=null, patSeries=null;
    if(inno){ patLabels=inno.labels; patSeries=inno.series.map((s,i)=>({name:s.name,color:i?'#0d9488':'#3b428f',values:s.values})); }
    const numOr0=(v)=>{ const n=Number(v); return isFinite(n)?n:0; };
    return {
      live:true,
      track:(cardVal('所属赛道'))||p.industry_name||'医药生物',
      risk:numOr0(cardVal('风险事件总数')),
      patent:numOr0(cardVal('专利总量')),
      nodes:numOr0(cardVal('股权节点数')),
      metrics:(p.metric_cards||[]).slice(0,6).map(m=>[m.label, this._fmtAmtStr(m.value), m.meta]),
      riskCards:(p.risk_cards||[]).map(c=>[c.label, (String(c.label).indexOf('金额')>=0)?this._fmtAmtStr(c.value):String(c.value)]),
      innovCards:(p.innovation_cards||[]).map(c=>[c.label, String(c.value)]),
      equityCards:(p.equity_cards||[]).map(c=>[c.label, String(c.value)]),
      summary:p.summary||'',
      trendLabels: trend?trend.labels:(ratio?ratio.labels:null), trendSeries,
      gmLabels: ratio?ratio.labels:null, gmSeries,
      patLabels, patSeries
    };
  }
  compareData(a,b,yi){
    const live=this._matched('compare');
    if(live && Array.isArray(live.rows) && live.rows.length && Array.isArray(live.company_names) && live.company_names.length>=2){
      const la=live.company_names[0], rb=live.company_names[1];
      const rows=live.rows.map(r=>{ const w=r.winner; const lW=w===la, rW=w===rb; return {metric:r.metric,left:this._fmtAmtStr(r.left_value),right:this._fmtAmtStr(r.right_value),winner:w,leftColor:lW?'var(--text)':'var(--text-2)',rightColor:rW?'var(--text)':'var(--text-2)',leftWin:lW?'600':'400',rightWin:rW?'600':'400'}; });
      const piv=this._pivot(live.chart);
      let barLabels=[], barSeries=[];
      if(piv){ barLabels=piv.labels.slice(0,4);
        const allv=piv.series.reduce((a,s)=>a.concat(s.values.slice(0,4)),[]).filter(v=>v!=null);
        const mxv=allv.length?Math.max.apply(null,allv.map(Math.abs)):0;
        const div=mxv>=1e6?1e8:1; // 后端金额为「元」量级时折算成亿元（图头单位即亿元）
        barSeries=piv.series.map(s=>({name:s.name,color:s.color,values:s.values.slice(0,4).map(v=>v!=null?v/div:null)})); }
      return {rows, barLabels, barSeries, summary:live.summary||''};
    }
    const pa=this.getProf(a), pb=this.getProf(b);
    // pa/pb 可能是 live 画像（无 rev/np/rd/gm/patents 等演示数组）；此时不可走演示对比计算，
    // 等 /api/compare 拉到再渲染（对比 tab 仅在 compare 页可见，会触发 loadCompare）。
    if(pa.live||pb.live) return {rows:[],barLabels:[],barSeries:[],summary:''};
    const def=[['营业收入(亿元)',pa.rev[yi],pb.rev[yi],'high'],['归母净利润(亿元)',pa.np[yi],pb.np[yi],'high'],['研发投入(亿元)',pa.rd[yi],pb.rd[yi],'high'],['销售毛利率(%)',pa.gm[yi],pb.gm[yi],'high'],['风险事件总数',pa.risk,pb.risk,'low'],['专利总量',pa.patent,pb.patent,'high']];
    let aw=0,bw=0;
    const fmt=v=>Number.isInteger(v)?this.nf(v):(+v).toFixed(1);
    const rows=def.map(r=>{ const lv=r[1],rv=r[2],dir=r[3]; let winner; if(lv===rv)winner='持平'; else { const aB=dir==='high'?lv>rv:lv<rv; winner=aB?a:b; aB?aw++:bw++; } const lW=winner===a, rW=winner===b; return {metric:r[0],left:fmt(lv),right:fmt(rv),winner,leftColor:lW?'var(--text)':'var(--text-2)',rightColor:rW?'var(--text)':'var(--text-2)',leftWin:lW?'600':'400',rightWin:rW?'600':'400'}; });
    return {rows,barLabels:['营业收入','归母净利润','研发投入'],barSeries:[{name:a,color:'#3b428f',values:[pa.rev[yi],pa.np[yi],pa.rd[yi]]},{name:b,color:'#0d9488',values:[pb.rev[yi],pb.np[yi],pb.rd[yi]]}],summary:a+' 领先 '+aw+' 项 · '+b+' 领先 '+bw+' 项'};
  }

  // ---- research ----
  _profReport(name, prof){
    const sty=(t)=> t==='h2'?'font-size:17.5px;font-weight:600;margin:24px 0 11px;color:var(--text)':(t==='li'?'display:flex;gap:10px;font-size:15px;line-height:1.78;color:var(--text-2);margin:0':'font-size:15px;line-height:1.85;color:var(--text-2);margin:0');
    const yr=prof.report_year||this.state.year;
    const raw=[['h2','一、公司概览'],['p', name+' 隶属 '+(prof.industry_name||'医药生物')+' 赛道，以下为基于结构化年报数据的关键画像（'+yr+' 年）。']];
    raw.push(['h2','二、关键财务指标']);
    (prof.metric_cards||[]).slice(0,6).forEach(m=>raw.push(['li', m.label+'：'+this._fmtAmtStr(m.value)+(m.meta?('（'+m.meta+'）'):'')]));
    if((prof.risk_cards||[]).length){ raw.push(['h2','三、风险维度']); prof.risk_cards.slice(0,5).forEach(c=>raw.push(['li', c.label+'：'+c.value])); }
    if((prof.innovation_cards||[]).length){ raw.push(['h2','四、创新维度']); prof.innovation_cards.slice(0,5).forEach(c=>raw.push(['li', c.label+'：'+c.value])); }
    if(prof.summary){ raw.push(['h2','五、画像摘要']); raw.push(['p', prof.summary]); }
    raw.push(['p','— 以上为结构化数据速览；点击上方「生成研究报告」可获得 DeepSeek 增强的完整研判与原文溯源。']);
    const blocks=raw.map(r=>({text:r[1],heading:r[0]==='h2',bullet:r[0]==='li',style:sty(r[0])}));
    const outline=raw.filter(r=>r[0]==='h2').map(r=>r[1]);
    // 引用来源：速览阶段未做 RAG，用该公司最新年度报告作为结构化数据来源
    const chunks=[];
    const ld=prof.latest_document;
    if(ld){ chunks.push({source: ld.title||ld.file_name||(name+' · 年度报告'), score:'结构化', doc_id:(ld.report_year?(ld.report_year+' 年报'):'年度报告'), text:'本速览的财务 / 风险 / 创新指标均来自该公司最新年度报告的结构化解析结果。点击「生成研究报告」可获得带原文切片的完整溯源。'}); }
    chunks.push({source: name+' · 结构化指标库', score:'SQL', doc_id:'fact_financial_report', text:'营收 / 利润 / 现金流 / 研发 / 净资产收益率 / 总资产 等指标取自结构化财务事实表（'+yr+' 年口径）。'});
    return {title:name+' · 经营质量速览（'+yr+'）', blocks, outline, chunks};
  }
  reportFor(name){
    const rd=(this.state.resData||{})[name];
    const raw=[
      ['h2','一、公司概览'],
      ['p',name+' 隶属医药生物（化学制药）赛道，主营创新药与仿制药的研发、生产与销售，研发驱动特征显著。'],
      ['h2','二、财务表现'],
      ['li','营业收入 279.9 亿元，同比 +22.6%，重回历史高位，集采影响逐步消化。'],
      ['li','归母净利润 63.4 亿元，同比 +47.5%，利润弹性显著高于收入增速。'],
      ['li','研发投入 65.8 亿元，研发强度约 23.5%，维持 A 股医药领先水平。'],
      ['li','销售毛利率 86.6%，同比 +1.7pct，盈利能力稳健。'],
      ['h2','三、同业对比'],
      ['p','与复星医药相比，'+name+' 营收体量偏小但盈利质量与研发强度明显占优，销售毛利率高出近 39 个百分点，风险事件数量更少。'],
      ['h2','四、风险提示'],
      ['li','应收账款周转天数同比上升约 9 天，需关注集采放量下的回款节奏。'],
      ['li','研发投入全部费用化，短期压低当期利润弹性。'],
      ['h2','五、结论与建议'],
      ['p','整体经营质量稳健回升，创新药放量是核心驱动；建议持续跟踪重点管线获批节奏与回款质量，并关注海外授权（License-out）进展。']
    ];
    const sty=(t)=> t==='h2'?'font-size:17.5px;font-weight:600;margin:24px 0 11px;color:var(--text)':(t==='li'?'display:flex;gap:10px;font-size:15px;line-height:1.78;color:var(--text-2);margin:0':'font-size:15px;line-height:1.85;color:var(--text-2);margin:0');
    const blocks=raw.map(r=>({text:r[1],heading:r[0]==='h2',bullet:r[0]==='li',style:sty(r[0])}));
    const outline=raw.filter(r=>r[0]==='h2').map(r=>r[1]);
    const chunks=[
      {source:name+' · 2024年年度报告',score:'0.912',doc_id:'MD-0042',text:'报告期内公司实现营业收入279.91亿元，同比增长22.63%……'},
      {source:name+' · 2024年年度报告',score:'0.864',doc_id:'MD-0118',text:'全年研发费用65.83亿元，创新药收入占比进一步提升……'},
      {source:name+' · 2024年年度报告',score:'0.802',doc_id:'MD-0203',text:'综合毛利率86.61%，期间费用结构持续优化……'},
      {source:'卫生健康统计年鉴 · 2024',score:'0.738',doc_id:'MACRO-0011',text:'全国卫生总费用持续增长，医药制造业景气度维持高位……'}
    ];
    if(rd && rd.report_markdown){
      const mdb=this._mdBlocks(rd.report_markdown);
      const lblocks=mdb.map(b=>({text:b.text,heading:b.t==='h2',bullet:b.t==='li',style:sty(b.t)}));
      const loutline=mdb.filter(b=>b.t==='h2').map(b=>b.text);
      let lchunks=this._chunkAdapt(rd.rag_chunks,true); if(!lchunks.length) lchunks=chunks;
      return {title:(rd.topic||(name+' · 经营质量研究简报')),blocks:lblocks,outline:loutline,chunks:lchunks};
    }
    const prof=this._resProfile(name);
    if(prof && prof.company_name) return this._profReport(prof.company_name, prof);
    return {title:name+' · 经营质量研究简报（2024）',blocks,outline,chunks};
  }
  genReport(){
    if(this.state.resLoading) return;
    const s=this.state;
    this.setState({resLoading:true,resDone:false});
    const done=(patch)=>this.setState(Object.assign({resLoading:false,resDone:true}, patch||{}));
    if(s.resMode==='batch'){
      const names=(s.resList||'').split(/[，,、\n]+/).map(x=>x.trim()).filter(Boolean).slice(0,5);
      this._apiPost('/api/batch-workflow',{company_names:names, report_year:s.year||null, top_k:s.topK||5})
        .then(d=>{ const rd=Object.assign({}, this.state.resData); (d.items||[]).forEach(it=>{ rd[it.company_name]={report_markdown:it.report_markdown, data_mode:it.data_mode, topic:it.topic, rag_chunks:[]}; }); done({resData:rd}); })
        .catch(()=>done());
    } else {
      const name=s.company;
      const topic=(s.resTopic&&s.resTopic.trim())||('请为 '+name+' 生成经营质量与风险诊断报告');
      this._apiPost('/api/workflow',{topic, company_name:name||null, report_year:s.year||null, top_k:s.topK||5})
        .then(d=>{ const rd=Object.assign({}, this.state.resData); rd[name]={report_markdown:d.report_markdown, data_mode:d.data_mode, topic:d.topic, sql:d.sql, sql_rows:d.sql_rows, rag_chunks:d.rag_chunks}; done({resData:rd}); })
        .catch(()=>done());
    }
  }
  downloadMd(name){ const rep=this.reportFor(name); let md='# '+rep.title+'\n\n'; rep.blocks.forEach(b=>{ md+=(b.heading?'## '+b.text:(b.bullet?'- '+b.text:b.text))+'\n\n'; }); try{ const a=document.createElement('a'); a.href=URL.createObjectURL(new Blob([md],{type:'text/markdown'})); a.download=name+'-研究简报.md'; a.click(); }catch(e){} }
  copyReport(name){ const rep=this.reportFor(name); let txt=rep.title+'\n\n'; rep.blocks.forEach(b=>{ txt+=(b.bullet?'• '+b.text:b.text)+'\n'; }); try{ navigator.clipboard.writeText(txt); }catch(e){} this.setState({resCopied:true,resExportOpen:false}); if(this._cpT)clearTimeout(this._cpT); this._cpT=setTimeout(()=>this.setState({resCopied:false}),1600); }
  printReport(){ try{ window.print(); }catch(e){} }

  // ---- demo storyline ----
  demoStepsDef(){ return [
    {t:'企业诊断',page:'compare',tab:'profile'},
    {t:'双公司比较',page:'compare',tab:'compare'},
    {t:'宏观联动',page:'advanced'},
    {t:'白盒溯源',page:'whitebox'},
    {t:'自动化报告',page:'research'}
  ]; }
  demoGo(i){ const d=this.demoStepsDef(); const c=Math.max(0,Math.min(d.length-1,i)); const st=d[c]; this.setState({page:st.page,cmpTab:st.tab||this.state.cmpTab,present:true,navOpen:false,demoStep:c,anim:0},()=>{ this.runCount(); this.loadPage(); }); }

  /*__METHODS__*/

  chatVals(){
    const s=this.state;
    const msgs=this.getMsgs();
    const active=this.state.chatActive;
    const vm=msgs.map((m,i)=>{
      const isAi=m.role==='ai';
      const isActive=isAi && i===active && !m.loading;
      return {
        isUser:m.role==='user', isAi, loading:!!m.loading, done:isAi&&!m.loading,
        text:m.text||'', route:m.resp?m.resp.route:'', active:isActive,
        blocks:(m.resp?m.resp.blocks:[]).map(b=>({text:b.text,bullet:b.t==='li',
          style:(b.t==='li'?'display:flex;gap:8px;font-size:13.5px;line-height:1.62;color:var(--text-2)':'font-size:13.5px;line-height:1.7;color:var(--text)')+';margin:0'})),
        wrapStyle:'cursor:pointer;border:1px solid '+(isActive?'var(--brand-400)':'var(--border)')+';background:var(--bg-elev);border-radius:4px 13px 13px 13px;padding:13px 16px;max-width:88%;transition:border-color .15s'+(isActive?';box-shadow:0 0 0 3px var(--brand-100)':''),
        onClick:()=>this.setState({chatActive:i})
      };
    });
    let resp=null; const am=msgs[active];
    if(am&&am.resp) resp=am.resp;
    if(!resp){ for(let i=msgs.length-1;i>=0;i--){ if(msgs[i].resp){ resp=msgs[i].resp; break; } } }
    const ev = resp?{has:true, route:resp.route, sql:resp.sql, cols:resp.cols,
      rows:resp.rows.map(r=>({cells:r})),
      chunks:resp.chunks.map(c=>({source:c.source,score:c.score.toFixed(3),doc_id:c.doc_id,text:c.text}))}:{has:false};
    const co=s.company, co2=(s.compareCompany&&s.compareCompany!==s.company)?s.compareCompany:'同业公司', yr=s.year;
    const sug=[
      {label:'企业诊断',q:'请总结 '+co+' '+yr+' 年的经营质量'},
      {label:'双公司对比',q:co+' 与 '+co2+' '+yr+' 年盈利能力差在哪'},
      {label:'宏观联动',q:'卫生总费用增长对 '+co+' 营收的拉动如何'},
      {label:'研发能力',q:co+' 的研发投入强度与在研管线情况'}
    ].map(x=>({label:x.label,onClick:()=>this.ask(x.q)}));
    const convs=this.state.chatConvs||[];
    const empty=(msgs.length===0);
    const sbOpen=this.state.chatSidebar!==false;
    const chat_convs=convs.map(c=>{ const act=c.id===this.state.chatConvId; return {
      cls:act?'dcv dcv-on':'dcv',
      title:(c.title||'新对话'),
      onClick:()=>this.switchChat(c.id),
      onDelete:(e)=>{ if(e&&e.stopPropagation) e.stopPropagation(); this.deleteChat(c.id); }
    }; });
    const ctxOn=this.state.chatCtxOn!==false;
    const model=this.state.chatModel||'flash';
    const seg='flex:1;height:28px;border-radius:6px;font-size:12px;font-weight:600;cursor:pointer;border:0;transition:all .12s;';
    return {
      chat_msgs:vm, chat_ev:ev, chat_evHas:ev.has, chat_loading:this.state.chatLoading,
      chat_input:this.state.chatInput,
      chat_onInput:(e)=>this.setState({chatInput:e.target.value}),
      chat_onKey:(e)=>{ const comp=(e.isComposing)||(e.nativeEvent&&e.nativeEvent.isComposing)||(e.keyCode===229); if(e.key==='Enter'&&!e.shiftKey&&!comp){ e.preventDefault(); this.send(); } },
      chat_send:()=>this.send(), chat_suggestions:sug,
      chat_convs:chat_convs, chat_hasConvs:convs.length>0,
      chat_new:()=>this.newChat(),
      chat_newStyle:'flex:1;height:34px;padding:0 10px;border-radius:9px;font-size:12.5px;font-weight:600;cursor:pointer;border:0;background:var(--brand-600);color:#fff;display:inline-flex;align-items:center;justify-content:center;gap:5px;white-space:nowrap',
      chat_newIconStyle:'width:34px;height:34px;border-radius:9px;border:0;background:var(--brand-600);color:#fff;cursor:pointer;font-size:18px;display:inline-flex;align-items:center;justify-content:center',
      chat_empty:empty, chat_chromeOp: empty?'0':'1',
      chat_sidebarOpen:sbOpen, chat_sidebarClosed:!sbOpen,
      chat_gridCols: empty?'0px 1fr 0px':(sbOpen?'238px 1fr 332px':'48px 1fr 332px'),
      chat_colStyle:'display:flex;flex-direction:column;min-width:0;height:calc(100vh - 178px)',
      chat_scrollStyle:'flex:1 1 0;min-height:0;overflow-y:auto;display:flex;flex-direction:column;gap:14px;padding:4px 6px 4px 2px',
      chat_bottomSpacer: empty?'1':'0',
      chat_welcomeStyle: empty?'text-align:center;opacity:1;max-height:170px;margin-bottom:20px;transition:opacity .3s ease,max-height .35s ease,margin-bottom .3s ease':'text-align:center;opacity:0;max-height:0;margin-bottom:0;overflow:hidden;transition:opacity .2s ease,max-height .3s ease,margin-bottom .3s ease',
      chat_toggleSidebar:()=>this.setState(st=>({chatSidebar:st.chatSidebar===false})),
      chat_collapseStyle:'width:30px;height:34px;border-radius:8px;border:1px solid var(--border);background:var(--bg-elev);color:var(--text-2);cursor:pointer;font-size:13px;flex-shrink:0;display:inline-flex;align-items:center;justify-content:center',
      chat_settingsOpen:!!this.state.chatSettings,
      chat_toggleSettings:()=>this.setState(st=>({chatSettings:!st.chatSettings})),
      chat_settingsBtnStyle:'width:100%;height:32px;border-radius:8px;border:1px solid var(--border);background:var(--bg-elev);color:var(--text-2);cursor:pointer;font-size:12px;display:inline-flex;align-items:center;justify-content:center;gap:6px',
      chat_model:model, chat_isFlash:model==='flash', chat_isPro:model==='pro',
      chat_modelHint: model==='pro'?'Pro · 深度分析(较慢)':'Flash · 快速',
      chat_setFlash:()=>this.setState({chatModel:'flash'}), chat_setPro:()=>this.setState({chatModel:'pro'}),
      chat_flashStyle:seg+(model==='flash'?'background:var(--brand-600);color:#fff':'background:transparent;color:var(--text-2)'),
      chat_proStyle:seg+(model==='pro'?'background:var(--brand-600);color:#fff':'background:transparent;color:var(--text-2)'),
      chat_ctxOn:ctxOn, chat_ctxLabel:ctxOn?'多轮上下文 · 已开启':'多轮上下文 · 已关闭',
      chat_ctxStyle:'width:100%;height:30px;border-radius:7px;cursor:pointer;font-size:12px;margin-bottom:7px;border:1px solid '+(ctxOn?'var(--brand-300)':'var(--border)')+';background:'+(ctxOn?'var(--brand-50)':'var(--bg-elev)')+';color:'+(ctxOn?'var(--brand-600)':'var(--text-2)'),
      chat_toggleCtx:()=>this.setState(st=>({chatCtxOn:st.chatCtxOn===false})),
      chat_clearAll:()=>this.clearAllChats(),
      chat_clearStyle:'width:100%;height:30px;border-radius:7px;cursor:pointer;font-size:12px;border:1px solid var(--neg-bg);background:var(--neg-bg);color:var(--neg)',
      chat_scrollRef:(el)=>{ this._chatScroll=el; }
    };
  }
  compareVals(){
    const s=this.state, yi=this.yi()<0?4:this.yi();
    const pa=this.getProf(s.company);
    const hasC=!!s.compareCompany;
    const tab=hasC?s.cmpTab:'profile';
    const tb='height:32px;padding:0 18px;border-radius:8px;font-size:13px;font-weight:500;cursor:pointer;border:0;transition:all .12s;';
    const act='background:var(--bg-elev);color:var(--text);box-shadow:0 1px 2px rgba(20,22,31,.08)';
    const ina='background:transparent;color:var(--text-2)';
    const cv=hasC?this.compareData(s.company,s.compareCompany,yi):{rows:[],barLabels:[],barSeries:[],summary:''};
    const comps=this._liveCompanies();
    let trendLabels, trendSeries, gmLabels, gmSeries, patLabels, patSeries;
    if(pa.live){
      trendLabels = (pa.trendLabels&&pa.trendLabels.length)?pa.trendLabels:[];
      trendSeries = pa.trendSeries||[];
      gmLabels = (pa.gmLabels&&pa.gmLabels.length)?pa.gmLabels:trendLabels;
      gmSeries = pa.gmSeries||[];
      patLabels = (pa.patLabels&&pa.patLabels.length)?pa.patLabels:[];
      patSeries = pa.patSeries||[];
    } else {
      trendLabels = this.D.trendYears;
      trendSeries = [{name:'营业收入',color:'#3b428f',values:pa.rev},{name:'归母净利润',color:'#0d9488',values:pa.np},{name:'研发投入',color:'#b45309',values:pa.rd}];
      gmLabels = this.D.trendYears; gmSeries = [{name:'销售毛利率',color:'#6d28d9',values:pa.gm}];
      patLabels = this.D.trendYears; patSeries = [{name:'发明专利',color:'#3b428f',values:pa.patents.inv},{name:'实用新型',color:'#0d9488',values:pa.patents.uti}];
    }
    return {
      cmp_isProfile:tab==='profile', cmp_isCompare:tab==='compare',
      cmp_title:hasC?(s.company+'  vs  '+s.compareCompany):(s.company+' · 全景画像'),
      cmp_company:s.company, cmp_other:s.compareCompany||'', cmp_hasCompare:hasC,
      cmp_initialA:s.company.slice(0,1), cmp_initialB:(s.compareCompany||'＋').slice(0,1),
      cmp_companies:comps,
      cmp_otherOptions:[{v:'',t:'（单公司画像）'}].concat(comps.filter(c=>c!==s.company).map(c=>({v:c,t:c}))),
      cmp_onCompany:(e)=>this.setParam({company:e.target.value}),
      cmp_onOther:(e)=>this.setParam({compareCompany:e.target.value}),
      cmp_setProfile:()=>this.setState({cmpTab:'profile'}),
      cmp_setCompare:()=>{ if(hasC) this.setState({cmpTab:'compare'}); },
      cmp_tabProfileStyle:tb+(tab==='profile'?act:ina),
      cmp_tabCompareStyle:tb+(tab==='compare'?act:(hasC?ina:'background:transparent;color:var(--gray-300);cursor:not-allowed')),
      cmp_overview:[['所属赛道',pa.track],['画像年份',String(s.year)],['风险事件总数',String(pa.risk)],['专利总量',this.nf(pa.patent)],['股权图谱节点',String(pa.nodes)]].map(o=>({label:o[0],value:o[1]})),
      cmp_metrics:pa.metrics.map(m=>({label:m[0],value:m[1],meta:m[2]})),
      cmp_summary:pa.summary,
      cmp_riskCards:pa.riskCards.map(c=>({label:c[0],value:c[1]})),
      cmp_innovCards:pa.innovCards.map(c=>({label:c[0],value:c[1]})),
      cmp_equityCards:pa.equityCards.map(c=>({label:c[0],value:c[1]})),
      cmp_trendLabels:trendLabels,
      cmp_trendSeries:trendSeries,
      cmp_gmLabels:gmLabels, cmp_gmSeries:gmSeries,
      cmp_patLabels:patLabels, cmp_patSeries:patSeries,
      cmp_rows:cv.rows, cmp_barLabels:cv.barLabels, cmp_barSeries:cv.barSeries, cmp_compSummary:cv.summary
    };
  }
  researchVals(){
    const s=this.state, mode=s.resMode;
    const list=(s.resList||'').split(/[，,、\n]+/).map(x=>x.trim()).filter(Boolean);
    const batchNames=list.slice(0,5);
    const activeName=mode==='batch'?(batchNames[s.resBatchActive]||batchNames[0]||s.company):s.company;
    this._ensureResProfile(activeName);
    const rep=this.reportFor(activeName);
    // data_mode 药丸：live 时根据真实生成模式映射「本地化文案 + 颜色」，否则按 DeepSeek 开关
    const liveMode=(this.state.resData && this.state.resData[activeName] && this.state.resData[activeName].data_mode)||null;
    const MODE={live:{t:'实时检索 · 增强',c:'var(--pos)',b:'var(--pos-bg)'},partial:{t:'部分接入 · 降级',c:'var(--warn)',b:'var(--warn-bg)'},degraded:{t:'本地降级合成',c:'var(--warn)',b:'var(--warn-bg)'},unavailable:{t:'无可用检索结果',c:'var(--neg)',b:'var(--neg-bg)'}};
    const modePill=liveMode?(MODE[liveMode]||{t:liveMode,c:'var(--warn)',b:'var(--warn-bg)'}):{t:(s.deepseek?'增强生成 · DeepSeek':'本地模板合成 · 降级'),c:(s.deepseek?'var(--pos)':'var(--warn)'),b:(s.deepseek?'var(--pos-bg)':'var(--warn-bg)')};
    const mb='flex:1;height:30px;border-radius:7px;font-size:12.5px;font-weight:500;cursor:pointer;border:0;transition:all .12s;';
    const on='background:var(--bg-elev);color:var(--text);box-shadow:0 1px 2px rgba(20,22,31,.08)';
    const off='background:transparent;color:var(--text-2)';
    // ---- 报告图表（按当前公司真实趋势；无数据回退演示）----
    const prof=this._resProfile(activeName);
    const tpiv=(prof&&prof.company_name)?this._pivot(prof.trend_chart):null;
    const sv=(nm)=>{ if(!tpiv) return null; const x=tpiv.series.find(z=>z.name===nm); return x?x.values:null; };
    let bars=null, linePts=null, areaPts=null, trendYears=null, trendLast=null;
    if(tpiv && tpiv.labels.length>=1){
      const L=tpiv.labels.length-1, P=Math.max(0,L-1);
      const rev=sv('营业收入'), np=sv('归属于上市公司股东的净利润'), rd=sv('研发费用');
      const amts=[rev,np,rd].filter(Boolean).reduce((a,arr)=>a.concat(arr.filter(v=>v!=null)),[]);
      const DIV=(amts.length&&Math.max.apply(null,amts.map(Math.abs))>=1e6)?1e8:1; // 元→亿元(已是亿元则不缩放)
      const Y=(v)=> v!=null? v/DIV : null;
      const finL=[{k:'营业收入',arr:rev},{k:'归母净利润',arr:np},{k:'研发投入',arr:rd}]
        .map(d=>({k:d.k, a:d.arr?Y(d.arr[P]):null, b:d.arr?Y(d.arr[L]):null})).filter(d=>d.b!=null);
      if(finL.length){
        const fmax=Math.max.apply(null, finL.map(d=>Math.max(Math.abs(d.a||0),Math.abs(d.b||0))))||1;
        bars=finL.map(d=>{ const a=d.a!=null?d.a:0, b=d.b; const delta=(d.a&&d.a!==0)?((b-a>=0?'+':'')+(((b-a)/Math.abs(a))*100).toFixed(1)+'%'):'—'; return {k:d.k,aH:(Math.abs(a)/fmax*100).toFixed(1)+'%',bH:(Math.abs(b)/fmax*100).toFixed(1)+'%',a:a.toFixed(1),b:b.toFixed(1),delta}; });
      }
      if(rev){
        const ys=tpiv.labels.map((y,i)=>[y, rev[i]!=null?rev[i]/DIV:null]).filter(d=>d[1]!=null);
        if(ys.length>=2){
          const vv=ys.map(d=>d[1]); let vmax=Math.max.apply(null,vv), vmin=Math.min.apply(null,vv);
          if(vmax===vmin){vmax+=1;vmin-=1;} const pad=(vmax-vmin)*0.18||1; vmax+=pad; vmin-=pad;
          const px=(i)=>(i/(ys.length-1))*100, py=(v)=>100-((v-vmin)/(vmax-vmin))*100;
          linePts=ys.map((d,i)=>px(i).toFixed(2)+','+py(d[1]).toFixed(2)).join(' ');
          areaPts='0,100 '+linePts+' 100,100';
          trendYears=ys.map(d=>({y:d[0],v:d[1].toFixed(1)})); trendLast=ys[ys.length-1][1].toFixed(1);
        }
      }
    }
    if(!bars){ const fin=[{k:'营业收入',a:228.2,b:279.9},{k:'归母净利润',a:43.0,b:63.4},{k:'研发投入',a:49.5,b:65.8}]; const fmax=Math.max.apply(null,fin.map(d=>Math.max(d.a,d.b))); bars=fin.map(d=>({k:d.k,aH:(d.a/fmax*100).toFixed(1)+'%',bH:(d.b/fmax*100).toFixed(1)+'%',a:d.a.toFixed(1),b:d.b.toFixed(1),delta:'+'+((d.b-d.a)/d.a*100).toFixed(1)+'%'})); }
    if(!linePts){ const yrs=[['2020',277.4],['2021',259.1],['2022',212.8],['2023',228.2],['2024',279.9]]; const vmax=290,vmin=200; const px=(i)=>(i/(yrs.length-1))*100, py=(v)=>100-((v-vmin)/(vmax-vmin))*100; linePts=yrs.map((y,i)=>px(i).toFixed(2)+','+py(y[1]).toFixed(2)).join(' '); areaPts='0,100 '+linePts+' 100,100'; trendYears=yrs.map(y=>({y:y[0],v:y[1].toFixed(1)})); trendLast=yrs[yrs.length-1][1].toFixed(1); }
    return {
      res_bars:bars,
      res_trendLine:linePts, res_trendArea:areaPts,
      res_trendYears:trendYears,
      res_trendLast:trendLast,
      res_isSingle:mode==='single', res_isBatch:mode==='batch',
      res_modeSingleStyle:mb+(mode==='single'?on:off), res_modeBatchStyle:mb+(mode==='batch'?on:off),
      res_setSingle:()=>this.setState({resMode:'single'}), res_setBatch:()=>this.setState({resMode:'batch'}),
      res_topic:s.resTopic, res_onTopic:(e)=>this.setState({resTopic:e.target.value}),
      res_topicPh:'例如：'+s.company+' 2024 年经营质量与研发能力研究',
      res_list:s.resList, res_onList:(e)=>this.setState({resList:e.target.value,resBatchActive:0}), res_listCount:batchNames.length,
      res_gen:()=>this.genReport(), res_loading:s.resLoading, res_notLoading:!s.resLoading, res_done:s.resDone,
      res_panelOpen:s.resPanelOpen!==false,
      res_togglePanel:()=>this.setState(st=>({resPanelOpen:st.resPanelOpen===false})),
      res_sourcesCount:rep.chunks.length,
      res_notCopied:!s.resCopied, res_copyLabel:s.resCopied?'已复制':'复制',
      res_sourcesBtnStyle:'height:34px;padding:0 12px;display:inline-flex;align-items:center;gap:6px;border-radius:9px;font-size:12.5px;font-weight:500;cursor:pointer;border:1px solid '+(s.resPanelOpen!==false?'var(--brand-300)':'var(--border)')+';background:'+(s.resPanelOpen!==false?'var(--brand-50)':'var(--bg-elev)')+';color:'+(s.resPanelOpen!==false?'var(--brand-600)':'var(--text-2)'),
      res_exportChevron:'transition:transform .15s'+(s.resExportOpen?';transform:rotate(180deg)':''),
      res_exportOpen:!!s.resExportOpen,
      res_toggleExport:()=>this.setState(st=>({resExportOpen:!st.resExportOpen})),
      res_copy:()=>this.copyReport(activeName), res_copied:!!s.resCopied,
      res_print:()=>{this.setState({resExportOpen:false});this.printReport();},
      res_dlMd:()=>{this.setState({resExportOpen:false});this.downloadMd(activeName);},
      res_genLabel:mode==='batch'?('生成批量报告（'+batchNames.length+' 家）'):'生成研究报告',
      res_title:rep.title, res_blocks:rep.blocks,
      res_outline:rep.outline.map(t=>({t})),
      res_dataMode:modePill.t,
      res_dataModeColor:modePill.c, res_dataModeBg:modePill.b,
      res_chunks:rep.chunks,
      res_batchNames:batchNames.map((n,i)=>({name:n,onClick:()=>this.setState({resBatchActive:i}),
        style:'text-align:left;width:100%;padding:8px 11px;border-radius:8px;font-size:12.5px;cursor:pointer;border:1px solid '+(i===s.resBatchActive?'var(--brand-300)':'var(--border)')+';background:'+(i===s.resBatchActive?'var(--brand-50)':'var(--bg-elev)')+';color:'+(i===s.resBatchActive?'var(--brand-600)':'var(--text-2)')+';font-weight:'+(i===s.resBatchActive?'600':'400')})),
      res_activeName:activeName,
      res_dl:()=>this.downloadMd(activeName)
    };
  }
  whiteboxVals(){
    const blk=(arr)=>arr.map(b=>({text:b.text,bullet:b.t==='li',style:(b.t==='li'?'display:flex;gap:9px;font-size:13.5px;line-height:1.65;color:var(--text-2)':'font-size:13.5px;line-height:1.7;color:var(--text)')+';margin:0'}));
    const reasoning=[
      {t:'li',text:'解析问题意图：识别为「研发投入」的同比变动 + 归因类问题，需先取数再结合年报佐证。'},
      {t:'li',text:'结构化检索：在 fact_financial 按 company=恒瑞医药、indicator=研发投入、year∈{2022,2023} 取数，得 48.9 → 49.5 亿元。'},
      {t:'li',text:'证据召回：在向量库检索年报「研发」相关切片，命中研发费用、在研管线与费用化政策说明。'},
      {t:'li',text:'交叉校验：SQL 数值与年报文字表述一致（49.5 亿元 / 同比约 +1.2%），无冲突。'},
      {t:'li',text:'归因合成：投入小幅增长但研发强度由 23.0% 降至 21.7%，主因营收增速（+7.2%）快于研发增速。'}
    ];
    const answer=[
      {t:'p',text:'结论：恒瑞医药 2023 年研发投入为 49.5 亿元，较 2022 年的 48.9 亿元小幅增长约 1.2%（增加 0.6 亿元）。'},
      {t:'li',text:'绝对额维持高位：连续多年研发投入居 A 股医药前列，全部费用化，口径稳健。'},
      {t:'li',text:'强度小幅回落：研发投入占营收比例由 23.0% 降至 21.7%，因营收同比增速更快。'},
      {t:'li',text:'结构性因素：部分早期管线临床阶段切换，使当期投入增速放缓。'}
    ];
    const chunks=[
      {source:'恒瑞医药 · 2023年年度报告',score:0.928,doc_id:'HRYY-2023-MD-0071',text:'报告期内公司研发费用为49.54亿元，持续保持高强度研发投入，研发费用全部计入当期损益……'},
      {source:'恒瑞医药 · 2023年年度报告',score:0.871,doc_id:'HRYY-2023-MD-0152',text:'公司在研创新药及改良型新药管线丰富，多个项目处于关键临床阶段，研发资源向重点管线倾斜……'},
      {source:'恒瑞医药 · 2022年年度报告',score:0.804,doc_id:'HRYY-2022-MD-0066',text:'上年度公司研发投入48.90亿元，研发投入占营业收入比例约22.98%……'}
    ];
    let _reasoning=reasoning, _answer=answer, _chunks=chunks;
    let _sql="SELECT indicator_name, report_year, value_num, unit\nFROM fact_financial\nWHERE company_name = '恒瑞医药'\n  AND indicator_name IN ('研发投入','营业收入')\n  AND report_year IN (2022, 2023)\nORDER BY indicator_name, report_year;";
    const wb=this._get('whitebox');
    if(wb){
      if(wb.reasoning_markdown) _reasoning=this._mdBlocks(wb.reasoning_markdown);
      if(wb.answer_markdown) _answer=this._mdBlocks(wb.answer_markdown);
      if(Array.isArray(wb.chunks)&&wb.chunks.length) _chunks=this._chunkAdapt(wb.chunks,false);
      if(wb.sql) _sql=wb.sql;
    }
    const stages=[
      {n:'1',title:'自然语言问题',tag:'输入',kind:'q',isQ:true,notLast:true},
      {n:'2',title:'路由与 SQL 执行',tag:'SQL Route',kind:'sql',isSql:true,notLast:true},
      {n:'3',title:'RAG 原文召回',tag:'Top '+this.state.topK,kind:'rag',isRag:true,notLast:true,chunks:_chunks.map(c=>({source:c.source,score:c.score.toFixed(3),doc_id:c.doc_id,text:c.text}))},
      {n:'4',title:'推理链路',tag:'Chain-of-Thought',kind:'reason',isReason:true,notLast:true,blocks:blk(_reasoning)},
      {n:'5',title:'最终结论',tag:'结论',kind:'answer',isAnswer:true,notLast:false,blocks:blk(_answer)}
    ];
    let wb_question='恒瑞医药 2023 年的研发投入相比上一年是增是减？变动幅度如何？主要影响因素有哪些？';
    if(wb){ const co=(Array.isArray(wb.chunks)&&wb.chunks[0]&&wb.chunks[0].metadata&&wb.chunks[0].metadata.company_name)||''; if(co) wb_question=co+' 最新年度核心经营指标的变动情况如何？请展示从结构化取数到原文佐证、再到结论的完整白盒链路。'; }
    return {
      wb_question:wb_question,
      wb_stages:stages,
      wb_sql:_sql,
      wb_cols: wb?[]:['指标','2022','2023','变动'],
      wb_rows: wb?[]:[{cells:['研发投入(亿元)','48.9','49.5','+1.2%']},{cells:['营业收入(亿元)','212.8','228.2','+7.2%']},{cells:['研发投入/营收','22.98%','21.69%','-1.29pct']}],
      wb_steps:[{l:'问题解析'},{l:'SQL 执行'},{l:'RAG 召回'},{l:'推理合成'},{l:'结论'}]
    };
  }
  _databaseLive(cat){
    const s=this.state;
    const catOf=(name)=>({dim:'维度表',fact:'事实表',dict:'字典表',map:'映射表'})[String(name||'').split('_')[0]]||'数据表';
    const q=(s.dbSearch||'').toLowerCase();
    const tables=cat.tables;
    const list=tables.filter(t=>!q||t.table_name.toLowerCase().includes(q)||catOf(t.table_name).toLowerCase().includes(q)).map(t=>({
      table_name:t.table_name, cn:catOf(t.table_name), rc:this.nf(t.row_count), cc:t.column_count, active:t.table_name===s.dbTable,
      onClick:()=>this.selectDbTable(t.table_name),
      style:'text-align:left;width:100%;padding:9px 11px;border-radius:9px;cursor:pointer;border:1px solid '+(t.table_name===s.dbTable?'var(--brand-300)':'transparent')+';background:'+(t.table_name===s.dbTable?'var(--brand-50)':'transparent')
    }));
    const meta=tables.find(t=>t.table_name===s.dbTable)||tables[0];
    const prevSlot=this._get('dbTable');
    const prev=(prevSlot && prevSlot.key===s.dbTable)?prevSlot.data:null;
    let db_cols, db_headers, db_rows, db_create, db_rc, db_cc;
    if(prev && Array.isArray(prev.columns)){
      db_cols=prev.columns.map(c=>({name:c.name,type:c.type,pk:!!c.is_pk}));
      db_headers=prev.columns.map(c=>c.name);
      db_rows=(prev.rows||[]).map(r=>({cells:prev.columns.map(c=>{ const v=r[c.name]; return v==null?'':String(v); })}));
      db_create=prev.create_sql||('CREATE TABLE '+s.dbTable+' ( … );');
      db_rc=this.nf(prev.row_count!=null?prev.row_count:(meta?meta.row_count:0));
      db_cc=prev.columns.length;
    } else {
      const cols=(meta&&meta.columns)||[];
      db_cols=cols.map(n=>({name:n,type:'',pk:false}));
      db_headers=cols.slice();
      db_rows=[];
      db_create='CREATE TABLE '+s.dbTable+' (\n'+cols.map(n=>'  '+n).join(',\n')+'\n);';
      db_rc=this.nf(meta?meta.row_count:0); db_cc=meta?meta.column_count:cols.length;
    }
    return {
      db_list:list, db_search:s.dbSearch, db_onSearch:(e)=>this.setState({dbSearch:e.target.value}),
      db_name:s.dbTable, db_cn:catOf(s.dbTable), db_rc, db_cc,
      db_create, db_cols, db_headers, db_rows
    };
  }
  databaseVals(){
    const s=this.state;
    const cat=this._get('dbCatalog');
    if(cat && Array.isArray(cat.tables) && cat.tables.length){ return this._databaseLive(cat); }
    const T={
      dim_company:{cn:'维度 · 公司',rc:48,cols:[['id','INTEGER',1],['company_name','TEXT',0],['industry_name','TEXT',0],['list_code','TEXT',0],['list_market','TEXT',0],['found_year','INTEGER',0],['province','TEXT',0]],rows:[['1','恒瑞医药','化学制药','600276','上证主板','1970','江苏'],['2','复星医药','化学制药','600196','上证主板','1994','上海'],['3','药明康德','医疗服务','603259','上证主板','2000','江苏'],['4','智飞生物','生物制品','300122','深证创业','2002','重庆'],['5','华兰生物','生物制品','002007','深证主板','1992','河南']]},
      dim_industry:{cn:'维度 · 行业',rc:24,cols:[['id','INTEGER',1],['industry_name','TEXT',0],['industry_level','INTEGER',0],['parent_name','TEXT',0]],rows:[['1','医药生物','1','—'],['2','化学制药','2','医药生物'],['3','生物制品','2','医药生物'],['4','中药','2','医药生物'],['5','医疗器械','2','医药生物']]},
      fact_financial:{cn:'事实 · 财务指标',rc:18642,cols:[['id','INTEGER',1],['company_name','TEXT',0],['report_year','INTEGER',0],['indicator_name','TEXT',0],['value_num','REAL',0],['unit','TEXT',0],['source_doc_id','TEXT',0]],rows:[['1','恒瑞医药','2024','营业收入','279.9','亿元','HRYY-2024'],['2','恒瑞医药','2024','归母净利润','63.4','亿元','HRYY-2024'],['3','恒瑞医药','2024','研发投入','65.8','亿元','HRYY-2024'],['4','复星医药','2024','营业收入','410.7','亿元','FXYY-2024'],['5','复星医药','2024','销售毛利率','47.8','%','FXYY-2024']]},
      fact_macro:{cn:'事实 · 宏观指标',rc:1286,cols:[['id','INTEGER',1],['indicator_name','TEXT',0],['period_year','INTEGER',0],['value_num','REAL',0],['unit','TEXT',0]],rows:[['1','卫生总费用','2024','90575.8','亿元'],['2','人均卫生费用','2024','6425.3','元'],['3','卫生总费用占GDP比重','2024','7.2','%']]},
      fact_patent:{cn:'事实 · 专利',rc:9420,cols:[['id','INTEGER',1],['company_name','TEXT',0],['patent_type','TEXT',0],['application_year','INTEGER',0],['patent_count','INTEGER',0]],rows:[['1','恒瑞医药','发明专利','2024','290'],['2','恒瑞医药','实用新型','2024','140'],['3','复星医药','发明专利','2024','196']]},
      doc_annual_report:{cn:'文档 · 年报',rc:312,cols:[['id','INTEGER',1],['company_name','TEXT',0],['report_year','INTEGER',0],['file_name','TEXT',0],['chunk_count','INTEGER',0],['updated_at','TEXT',0]],rows:[['1','恒瑞医药','2024','恒瑞医药2024年年度报告.pdf','842','2025-04-12'],['2','复星医药','2024','复星医药2024年年度报告.pdf','1036','2025-04-15']]}
    };
    const order=['dim_company','dim_industry','fact_financial','fact_macro','fact_patent','doc_annual_report'];
    const q=(s.dbSearch||'').toLowerCase();
    const list=order.filter(k=>!q||k.includes(q)||T[k].cn.toLowerCase().includes(q)).map(k=>({
      table_name:k, cn:T[k].cn, rc:this.nf(T[k].rc), cc:T[k].cols.length, active:k===s.dbTable,
      onClick:()=>this.setState({dbTable:k}),
      style:'text-align:left;width:100%;padding:9px 11px;border-radius:9px;cursor:pointer;border:1px solid '+(k===s.dbTable?'var(--brand-300)':'transparent')+';background:'+(k===s.dbTable?'var(--brand-50)':'transparent')
    }));
    const act=T[s.dbTable]||T.fact_financial;
    const create='CREATE TABLE '+s.dbTable+' (\n'+act.cols.map(c=>'  '+c[0]+' '+c[1]+(c[2]?' PRIMARY KEY':'')).join(',\n')+'\n);';
    return {
      db_list:list, db_search:s.dbSearch, db_onSearch:(e)=>this.setState({dbSearch:e.target.value}),
      db_name:s.dbTable, db_cn:act.cn, db_rc:this.nf(act.rc), db_cc:act.cols.length,
      db_create:create,
      db_cols:act.cols.map(c=>({name:c[0],type:c[1],pk:!!c[2]})),
      db_headers:act.cols.map(c=>c[0]),
      db_rows:act.rows.map(r=>({cells:r}))
    };
  }
  timelineVals(){
    const C={'财务':{c:'var(--series-1)',b:'var(--brand-50)'},'风险':{c:'var(--neg)',b:'var(--neg-bg)'},'创新':{c:'var(--series-2)',b:'rgba(13,148,136,.12)'}};
    const slot=this._get('timeline');
    const live=slot?slot.data:null;
    if(live && Array.isArray(live.events) && live.events.length){
      const colorFor=(label)=>{ const l=String(label||''); if(l.indexOf('风险')>=0) return 'var(--neg)'; if(l.indexOf('创新')>=0) return 'var(--series-2)'; return 'var(--series-1)'; };
      const tl_cards=(live.cards||[]).map(c=>({label:c.label, value:String(c.value), color:colorFor(c.label)}));
      const shortInd=(s)=>String(s||'').replace('归属于上市公司股东的净利润','归母净利润').replace('经营活动产生的现金流量净额','经营现金流');
      const tl_events=live.events.map(e=>{ const cc=C[e.category]||C['财务']; const det=(e.category==='财务')?this._fmtAmtStr(e.detail):e.detail; return {date:e.event_date, category:e.category, title:shortInd(e.title), detail:det, catColor:cc.c, catBg:cc.b}; });
      return {tl_cards, tl_events};
    }
    const ev=[
      ['2024-12-18','创新','瑞维鲁胺新适应症获批上市','转移性激素敏感性前列腺癌适应症获 NMPA 批准，进一步打开商业化空间。'],
      ['2024-10-30','财务','发布 2024 年三季度报告','前三季度营业收入同比增长约 18%，归母净利润延续高增长。'],
      ['2024-08-12','风险','收到交易所年报问询函','就研发资本化口径与销售费用结构作出说明，已按期回复，无后续处罚。'],
      ['2024-06-05','创新','GLP-1 类创新药 III 期临床达主要终点','减重与降糖双适应症推进，进入 NDA 申报准备阶段。'],
      ['2024-03-28','财务','披露 2023 年年度报告','全年研发投入 49.5 亿元，研发费用全部费用化，毛利率 84.9%。'],
      ['2023-11-20','创新','达成海外 License-out 合作','向跨国药企授权创新药海外权益，获首付款及里程碑付款。'],
      ['2023-09-15','风险','应收账款周转放缓预警','应收账款周转天数同比上升，触发中优先级财务预警信号。']
    ];
    return {
      tl_cards:[{label:'财务事件',value:'3',color:'var(--series-1)'},{label:'风险事件',value:'2',color:'var(--neg)'},{label:'创新事件',value:'2',color:'var(--series-2)'}],
      tl_events:ev.map(e=>({date:e[0],category:e[1],title:e[2],detail:e[3],catColor:C[e[1]].c,catBg:C[e[1]].b}))
    };
  }
  advancedVals(){
    const s=this.state;
    const C={brand:'var(--brand-600)',s2:'var(--series-2)',s3:'var(--series-3)'};
    const ad0=this.state.advData;
    let defs;
    if(ad0 && ad0.tool_results && ad0.tool_results.equity && Array.isArray(ad0.tool_results.equity.nodes)){
      const eq=ad0.tool_results.equity, rootName=eq.root_company||s.company;
      const ratioOf={}; (eq.edges||[]).forEach(e=>{ if(e&&e.target!=null) ratioOf[e.target]=e.ratio; });
      const seen={}, sub=[];
      eq.nodes.forEach(n=>{ if(!n||n.level===0||n.type==='root'||n.name===rootName||seen[n.name]) return; seen[n.name]=1; sub.push(n); });
      defs=sub.slice(0,6).map(n=>{ const rr=ratioOf[n.id]; const rel=n.type==='person'?'自然人股东':((rr!=null&&rr>=50)?'控股子公司':'关联方'); const nm=n.name+(rr!=null?(' · '+Number(rr).toFixed(Number(rr)%1?1:0)+'%'):''); const col=n.type==='person'?'s3':((rr!=null&&rr>=50)?'brand':'s2'); return [rel,nm,col]; });
      if(!defs.length) defs=[['股权穿透','运行后暂无下属/关联节点','brand']];
    } else {
      defs=[['控股股东','恒瑞医药集团 · 24.1%','brand'],['一致行动人','天广实生物','brand'],['全资子公司','成都盛迪医药','s2'],['全资子公司','上海恒瑞医药','s2'],['控股子公司','苏州盛迪亚生物','s2'],['海外平台','Luzsana Biotech','s3']];
    }
    const ang=[-90,-30,30,90,150,210], r=36;
    const nodes=defs.map((d,i)=>{ const a=ang[i]*Math.PI/180; const x=50+r*Math.cos(a), y=50+r*Math.sin(a); return {rel:d[0],name:d[1],color:C[d[2]],x:x.toFixed(2),y:y.toFixed(2),pos:'left:'+x.toFixed(2)+'%;top:'+y.toFixed(2)+'%'}; });
    const edges=nodes.map(n=>({x1:50,y1:50,x2:n.x,y2:n.y}));
    const prof=this._matched('profile');
    let adv_tools;
    if(prof && Array.isArray(prof.equity_cards) && prof.equity_cards.length){
      const eq=(label)=>{ const c=prof.equity_cards.find(x=>x.label===label); return c?String(c.value):'-'; };
      const cardv=(label)=>{ const c=(prof.cards||[]).find(x=>x.label===label); return c?String(c.value):'-'; };
      adv_tools=[{label:'图谱节点',value:eq('图谱节点')},{label:'关系边',value:eq('图谱边数')},{label:'一级关系',value:eq('一级关系')},{label:'司法风险',value:cardv('风险事件总数')}];
    } else {
      adv_tools=[{label:'图谱节点',value:'47'},{label:'关系边',value:'86'},{label:'一级关系',value:'12'},{label:'司法风险',value:'4'}];
    }
    const ad=this.state.advData;
    let adv_answer;
    if(ad && ad.answer_markdown){
      const pStyle='font-size:13.5px;line-height:1.75;color:var(--text-2);margin:0';
      const liStyle='display:flex;gap:9px;font-size:13.5px;line-height:1.7;color:var(--text-2);margin:0';
      adv_answer=this._mdBlocks(ad.answer_markdown).map(b=>({text:b.text,bullet:b.t==='li',style:b.t==='li'?liStyle:pStyle}));
    } else {
      adv_answer=[
        {text:'股权结构以恒瑞医药集团为控股股东（约 24.1%），下设多家全资 / 控股研发与生产子公司，并通过海外平台 Luzsana 承接国际化布局，整体股权清晰、控制权稳定。',bullet:false,style:'font-size:13.5px;line-height:1.75;color:var(--text-2);margin:0'},
        {text:'创新能力维度评分领先：发明专利与在研管线储备充足，研发人员规模与对外合作（License-out）活跃度构成核心壁垒。',bullet:true,style:'display:flex;gap:9px;font-size:13.5px;line-height:1.7;color:var(--text-2);margin:0'},
        {text:'潜在风险：海外子公司经营受汇率与监管环境影响，需关注跨境关联交易与商誉减值敞口。',bullet:true,style:'display:flex;gap:9px;font-size:13.5px;line-height:1.7;color:var(--text-2);margin:0'}
      ];
    }
    return {
      adv_question:s.advQ!=null?s.advQ:('请分析'+s.company+'的股权结构与创新能力，并指出潜在风险点'),
      adv_onQuestion:(e)=>this.setState({advQ:e.target.value}),
      adv_company:s.company,
      adv_run:()=>{ if(this.state.advLoading)return; const s2=this.state; const q=(s2.advQ!=null?s2.advQ:('请分析'+s2.company+'的股权结构与创新能力，并指出潜在风险点')); this.setState({advLoading:true,advDone:false}); this._apiPost('/api/advanced',{question:q, company_name:s2.company}).then(d=>this.setState({advLoading:false,advDone:true,advData:d})).catch(()=>{ if(this._advT)clearTimeout(this._advT); this._advT=setTimeout(()=>this.setState({advLoading:false,advDone:true}),900); }); },
      adv_loading:s.advLoading, adv_done:s.advDone,
      adv_nodes:nodes, adv_edges:edges,
      adv_tools:adv_tools,
      adv_answer:adv_answer,
      adv_innovLabels:['发明专利','在研管线','研发人员','对外合作'],
      adv_innovSeries:[{name:'创新能力维度评分',color:'#6d28d9',values:[88,82,79,71]}]
    };
  }

  renderVals(){
    return Object.assign({}, this.shellVals(), this.todayVals(), this.chatVals(), this.compareVals(), this.researchVals(), this.whiteboxVals(), this.databaseVals(), this.timelineVals(), this.advancedVals());
  }
}
