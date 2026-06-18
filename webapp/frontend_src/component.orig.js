
class Component extends DCLogic {
  state = {
    page:'today', theme:'light', present:false, navOpen:false,
    company:'恒瑞医药', compareCompany:'复星医药', year:2024, scope:'industry', topK:5, demoStep:0,
    deepseek:true, anim:0,
    chatMsgs:null, chatInput:'', chatActive:0, chatLoading:false,
    cmpTab:'profile',
    resMode:'single', resTopic:'', resList:'恒瑞医药、复星医药、药明康德', resLoading:false, resDone:true, resBatchActive:0,
    wbTab:'flow',
    dbTable:'fact_financial', dbSearch:'',
    advLoading:false, advDone:true
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

  go(p){ this.setState({page:p, navOpen:false, anim:0}, ()=>this.runCount()); }
  runCount(){
    if(this._raf) cancelAnimationFrame(this._raf);
    if(window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches){ this.setState({anim:1}); return; }
    const t0=performance.now(), dur=820;
    const tick=(t)=>{ let k=Math.min(1,(t-t0)/dur); k=1-Math.pow(1-k,3); this.setState({anim:k}); if(k<1) this._raf=requestAnimationFrame(tick); };
    this._raf=requestAnimationFrame(tick);
  }
  componentDidMount(){ this.runCount(); }

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
      company:s.company, year:s.year, topK:s.topK, companies:this.D.companies, years:this.D.years,
      isToday:s.page==='today', isChat:s.page==='chat', isCompare:s.page==='compare', isResearch:s.page==='research', isWhitebox:s.page==='whitebox', isDatabase:s.page==='database', isTimeline:s.page==='timeline', isAdvanced:s.page==='advanced',
      themeIcon: s.theme==='dark'?['M12 3a6 6 0 0 0 9 9 9 9 0 1 1-9-9z']:['M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M6.3 17.7l-1.4 1.4M19.1 4.9l-1.4 1.4','M12 8a4 4 0 1 0 0 8 4 4 0 0 0 0-8z'],
      toggleTheme:()=>this.setState({theme:s.theme==='dark'?'light':'dark'}),
      togglePresent:()=>this.setState({present:!s.present}),
      toggleMode:()=>this.setState({deepseek:!s.deepseek}),
      openNav:()=>this.setState({navOpen:true}), closeNav:()=>this.setState({navOpen:false}),
      onCompany:(e)=>this.setState({company:e.target.value,anim:0},()=>this.runCount()),
      onYear:(e)=>this.setState({year:Number(e.target.value),anim:0},()=>this.runCount()),
      onScopeInd:()=>this.setState({scope:'industry'}), onScopeAll:()=>this.setState({scope:'all'}),
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
    const today_kpis=[
      {label:'覆盖企业',value:this.cu(D.stats.companies),hint:'医药生物 6 大细分',icon:ic.biz},
      {label:'年报文档',value:this.cu(D.stats.documents),hint:'2020–2024 全量入库',icon:ic.doc},
      {label:'财务事实',value:this.nf(this.cu(D.stats.financial_facts)),hint:'结构化指标条目',icon:ic.fact},
      {label:'宏观指标',value:this.nf(this.cu(D.stats.macro_facts)),hint:'卫生类联动数据',icon:ic.macro}
    ];
    const sc=(k)=>()=>this.go(k);
    const today_scenes=[
      {title:'智能问答',desc:'自然语言提问，自动路由 SQL / RAG / 宏观，回答附带可追溯证据。',cta:'去提问',onClick:sc('chat'),tint:'var(--series-1)',tintBg:'var(--brand-50)',icon:['M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z']},
      {title:'深度研究',desc:'一键编排「检索→抽取→合成→校验」，产出可下载的 Markdown 研报。',cta:'生成研报',onClick:sc('research'),tint:'var(--series-2)',tintBg:'rgba(13,148,136,.1)',icon:['M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z','M14 2v6h6','M9 13h6','M9 17h6']},
      {title:'公司画像 · 对比',desc:'单家全景画像，或与同业对手做多指标横向对比与可视化。',cta:'看对比',onClick:sc('compare'),tint:'var(--series-4)',tintBg:'rgba(109,40,217,.1)',icon:['M4 4h6v16H4zM14 4h6v16h-6z']},
      {title:'白盒溯源',desc:'公开 SQL、RAG 原文切片与推理链路，每个结论都能回看来路。',cta:'看链路',onClick:sc('whitebox'),tint:'var(--series-3)',tintBg:'rgba(180,83,9,.1)',icon:['M3 7V5a2 2 0 0 1 2-2h2','M17 3h2a2 2 0 0 1 2 2v2','M21 17v2a2 2 0 0 1-2 2h-2','M7 21H5a2 2 0 0 1-2-2v-2','M7 12h10']}
    ];
    const mx=Math.max.apply(null,D.ranking.map(r=>r.value));
    const today_ranking=D.ranking.map((r,i)=>({rank:i+1,name:r.name,value:r.value.toFixed(1),pct:(r.value/mx*100).toFixed(0),sel:!!r.sel,
      weight:r.sel?'600':'500',nameColor:r.sel?'var(--brand-600)':'var(--text)',barColor:r.sel?'var(--brand-600)':'var(--gray-300)'}));
    const sev={'高':{c:'var(--neg)',b:'var(--neg-bg)'},'中':{c:'var(--warn)',b:'var(--warn-bg)'},'低':{c:'var(--info)',b:'var(--info-bg)'}};
    const today_alerts=D.alerts.map(a=>({severity:a.severity,company:a.company,year:a.year,signal:a.signal,detail:a.detail,sevColor:sev[a.severity].c,sevBg:sev[a.severity].b}));
    const dgn=(arr)=>{ const cur=arr[yi], prev=arr[yi-1]; if(prev==null) return {t:'—',pos:true}; const d=(cur-prev)/Math.abs(prev)*100; return {t:(d>=0?'+':'')+d.toFixed(1)+'%',pos:d>=0}; };
    const mk=(label,arr,unit,pct)=>{ const g=pct?{t:(arr[yi]-arr[yi-1]>=0?'+':'')+(arr[yi]-arr[yi-1]).toFixed(1)+'pct',pos:arr[yi]-arr[yi-1]>=0}:dgn(arr); return {label,value:this.cu(arr[yi],1),unit,delta:g.t,deltaColor:g.pos?'var(--pos)':'var(--neg)'}; };
    const today_metrics=[ mk('营业收入',D.rev,'亿元'), mk('归母净利润',D.np,'亿元'), mk('研发投入',D.rd,'亿元'), mk('销售毛利率',D.gm,'%',true) ];
    return {
      today_kpis, today_scenes, today_ranking, today_alerts, today_metrics,
      today_industry:'化学制药', today_rankScope:s.scope==='industry'?'同一级行业排名':'全行业排名', today_rankN:18,
      today_alertSummary:'共 16 条信号 · 高优先级 3 · 覆盖 9 家',
      today_trendLabels:D.trendYears,
      today_trendSeries:[{name:'营业收入',color:'#3b428f',values:D.rev}]
    };
  }

  // ---- chat ----
  getMsgs(){ return this.state.chatMsgs || this.seedChat(); }
  seedChat(){ return [
    {role:'user',text:'请总结恒瑞医药 2024 年的经营质量'},
    {role:'ai',loading:false,resp:this.answerFor('经营质量')}
  ]; }
  ask(q){
    const msgs=this.getMsgs().slice();
    msgs.push({role:'user',text:q});
    const ai=msgs.length;
    msgs.push({role:'ai',loading:true,resp:null});
    this.setState({chatMsgs:msgs,chatInput:'',chatActive:ai,chatLoading:true});
    if(this._chatT) clearTimeout(this._chatT);
    this._chatT=setTimeout(()=>{
      const m2=this.getMsgs().slice();
      m2[ai]={role:'ai',loading:false,resp:this.answerFor(q)};
      this.setState({chatMsgs:m2,chatLoading:false});
    },1150);
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
    return base[name]||base['恒瑞医药'];
  }
  compareData(a,b,yi){
    const pa=this.getProf(a), pb=this.getProf(b);
    const def=[['营业收入(亿元)',pa.rev[yi],pb.rev[yi],'high'],['归母净利润(亿元)',pa.np[yi],pb.np[yi],'high'],['研发投入(亿元)',pa.rd[yi],pb.rd[yi],'high'],['销售毛利率(%)',pa.gm[yi],pb.gm[yi],'high'],['风险事件总数',pa.risk,pb.risk,'low'],['专利总量',pa.patent,pb.patent,'high']];
    let aw=0,bw=0;
    const fmt=v=>Number.isInteger(v)?this.nf(v):(+v).toFixed(1);
    const rows=def.map(r=>{ const lv=r[1],rv=r[2],dir=r[3]; let winner; if(lv===rv)winner='持平'; else { const aB=dir==='high'?lv>rv:lv<rv; winner=aB?a:b; aB?aw++:bw++; } const lW=winner===a, rW=winner===b; return {metric:r[0],left:fmt(lv),right:fmt(rv),winner,leftColor:lW?'var(--text)':'var(--text-2)',rightColor:rW?'var(--text)':'var(--text-2)',leftWin:lW?'600':'400',rightWin:rW?'600':'400'}; });
    return {rows,barLabels:['营业收入','归母净利润','研发投入'],barSeries:[{name:a,color:'#3b428f',values:[pa.rev[yi],pa.np[yi],pa.rd[yi]]},{name:b,color:'#0d9488',values:[pb.rev[yi],pb.np[yi],pb.rd[yi]]}],summary:a+' 领先 '+aw+' 项 · '+b+' 领先 '+bw+' 项'};
  }

  // ---- research ----
  reportFor(name){
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
    return {title:name+' · 经营质量研究简报（2024）',blocks,outline,chunks};
  }
  genReport(){ if(this.state.resLoading)return; this.setState({resLoading:true,resDone:false}); if(this._resT)clearTimeout(this._resT); this._resT=setTimeout(()=>this.setState({resLoading:false,resDone:true}),1300); }
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
  demoGo(i){ const d=this.demoStepsDef(); const c=Math.max(0,Math.min(d.length-1,i)); const st=d[c]; this.setState({page:st.page,cmpTab:st.tab||this.state.cmpTab,present:true,navOpen:false,demoStep:c,anim:0},()=>this.runCount()); }

  /*__METHODS__*/

  chatVals(){
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
    const sug=[
      {label:'企业诊断',q:'请总结恒瑞医药 2024 年的经营质量'},
      {label:'双公司对比',q:'恒瑞医药与复星医药 2024 年盈利能力差在哪'},
      {label:'宏观联动',q:'卫生总费用增长对医药企业营收的拉动如何'},
      {label:'研发能力',q:'恒瑞医药的研发投入强度与在研管线情况'}
    ].map(x=>({label:x.label,onClick:()=>this.ask(x.q)}));
    return {
      chat_msgs:vm, chat_ev:ev, chat_evHas:ev.has, chat_loading:this.state.chatLoading,
      chat_input:this.state.chatInput,
      chat_onInput:(e)=>this.setState({chatInput:e.target.value}),
      chat_onKey:(e)=>{ if((e.metaKey||e.ctrlKey)&&e.key==='Enter'){ e.preventDefault(); this.send(); } },
      chat_send:()=>this.send(), chat_suggestions:sug,
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
    return {
      cmp_isProfile:tab==='profile', cmp_isCompare:tab==='compare',
      cmp_title:hasC?(s.company+'  vs  '+s.compareCompany):(s.company+' · 全景画像'),
      cmp_company:s.company, cmp_other:s.compareCompany||'', cmp_hasCompare:hasC,
      cmp_initialA:s.company.slice(0,1), cmp_initialB:(s.compareCompany||'＋').slice(0,1),
      cmp_companies:this.D.companies,
      cmp_otherOptions:[{v:'',t:'（单公司画像）'}].concat(this.D.companies.filter(c=>c!==s.company).map(c=>({v:c,t:c}))),
      cmp_onCompany:(e)=>this.setState({company:e.target.value,anim:0},()=>this.runCount()),
      cmp_onOther:(e)=>this.setState({compareCompany:e.target.value}),
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
      cmp_trendLabels:this.D.trendYears,
      cmp_trendSeries:[{name:'营业收入',color:'#3b428f',values:pa.rev},{name:'归母净利润',color:'#0d9488',values:pa.np},{name:'研发投入',color:'#b45309',values:pa.rd}],
      cmp_gmLabels:this.D.trendYears, cmp_gmSeries:[{name:'销售毛利率',color:'#6d28d9',values:pa.gm}],
      cmp_patLabels:this.D.trendYears, cmp_patSeries:[{name:'发明专利',color:'#3b428f',values:pa.patents.inv},{name:'实用新型',color:'#0d9488',values:pa.patents.uti}],
      cmp_rows:cv.rows, cmp_barLabels:cv.barLabels, cmp_barSeries:cv.barSeries, cmp_compSummary:cv.summary
    };
  }
  researchVals(){
    const s=this.state, mode=s.resMode;
    const list=(s.resList||'').split(/[，,、\n]+/).map(x=>x.trim()).filter(Boolean);
    const batchNames=list.slice(0,5);
    const activeName=mode==='batch'?(batchNames[s.resBatchActive]||batchNames[0]||s.company):s.company;
    const rep=this.reportFor(activeName);
    const mb='flex:1;height:30px;border-radius:7px;font-size:12.5px;font-weight:500;cursor:pointer;border:0;transition:all .12s;';
    const on='background:var(--bg-elev);color:var(--text);box-shadow:0 1px 2px rgba(20,22,31,.08)';
    const off='background:transparent;color:var(--text-2)';
    // ---- 报告图表 ----
    const fin=[{k:'营业收入',a:228.2,b:279.9},{k:'归母净利润',a:43.0,b:63.4},{k:'研发投入',a:49.5,b:65.8}];
    const fmax=Math.max.apply(null,fin.map(d=>Math.max(d.a,d.b)));
    const bars=fin.map(d=>({k:d.k,aH:(d.a/fmax*100).toFixed(1)+'%',bH:(d.b/fmax*100).toFixed(1)+'%',a:d.a.toFixed(1),b:d.b.toFixed(1),delta:'+'+((d.b-d.a)/d.a*100).toFixed(1)+'%'}));
    const yrs=[['2020',277.4],['2021',259.1],['2022',212.8],['2023',228.2],['2024',279.9]];
    const vmax=290,vmin=200;
    const px=(i)=>(i/(yrs.length-1))*100, py=(v)=>100-((v-vmin)/(vmax-vmin))*100;
    const linePts=yrs.map((y,i)=>px(i).toFixed(2)+','+py(y[1]).toFixed(2)).join(' ');
    const areaPts='0,100 '+linePts+' 100,100';
    return {
      res_bars:bars,
      res_trendLine:linePts, res_trendArea:areaPts,
      res_trendYears:yrs.map(y=>({y:y[0],v:y[1].toFixed(1)})),
      res_trendLast:yrs[yrs.length-1][1].toFixed(1),
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
      res_dataMode:s.deepseek?'增强生成 · DeepSeek':'本地模板合成 · 降级',
      res_dataModeColor:s.deepseek?'var(--pos)':'var(--warn)', res_dataModeBg:s.deepseek?'var(--pos-bg)':'var(--warn-bg)',
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
    const stages=[
      {n:'1',title:'自然语言问题',tag:'输入',kind:'q',isQ:true,notLast:true},
      {n:'2',title:'路由与 SQL 执行',tag:'SQL Route',kind:'sql',isSql:true,notLast:true},
      {n:'3',title:'RAG 原文召回',tag:'Top '+this.state.topK,kind:'rag',isRag:true,notLast:true,chunks:chunks.map(c=>({source:c.source,score:c.score.toFixed(3),doc_id:c.doc_id,text:c.text}))},
      {n:'4',title:'推理链路',tag:'Chain-of-Thought',kind:'reason',isReason:true,notLast:true,blocks:blk(reasoning)},
      {n:'5',title:'最终结论',tag:'结论',kind:'answer',isAnswer:true,notLast:false,blocks:blk(answer)}
    ];
    return {
      wb_question:'恒瑞医药 2023 年的研发投入相比上一年是增是减？变动幅度如何？主要影响因素有哪些？',
      wb_stages:stages,
      wb_sql:"SELECT indicator_name, report_year, value_num, unit\nFROM fact_financial\nWHERE company_name = '恒瑞医药'\n  AND indicator_name IN ('研发投入','营业收入')\n  AND report_year IN (2022, 2023)\nORDER BY indicator_name, report_year;",
      wb_cols:['指标','2022','2023','变动'],
      wb_rows:[{cells:['研发投入(亿元)','48.9','49.5','+1.2%']},{cells:['营业收入(亿元)','212.8','228.2','+7.2%']},{cells:['研发投入/营收','22.98%','21.69%','-1.29pct']}],
      wb_steps:[{l:'问题解析'},{l:'SQL 执行'},{l:'RAG 召回'},{l:'推理合成'},{l:'结论'}]
    };
  }
  databaseVals(){
    const s=this.state;
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
    const defs=[['控股股东','恒瑞医药集团 · 24.1%','brand'],['一致行动人','天广实生物','brand'],['全资子公司','成都盛迪医药','s2'],['全资子公司','上海恒瑞医药','s2'],['控股子公司','苏州盛迪亚生物','s2'],['海外平台','Luzsana Biotech','s3']];
    const ang=[-90,-30,30,90,150,210], r=36;
    const nodes=defs.map((d,i)=>{ const a=ang[i]*Math.PI/180; const x=50+r*Math.cos(a), y=50+r*Math.sin(a); return {rel:d[0],name:d[1],color:C[d[2]],x:x.toFixed(2),y:y.toFixed(2),pos:'left:'+x.toFixed(2)+'%;top:'+y.toFixed(2)+'%'}; });
    const edges=nodes.map(n=>({x1:50,y1:50,x2:n.x,y2:n.y}));
    return {
      adv_question:s.advQ!=null?s.advQ:'请分析恒瑞医药的股权结构与创新能力，并指出潜在风险点',
      adv_onQuestion:(e)=>this.setState({advQ:e.target.value}),
      adv_company:s.company,
      adv_run:()=>{ if(this.state.advLoading)return; this.setState({advLoading:true,advDone:false}); if(this._advT)clearTimeout(this._advT); this._advT=setTimeout(()=>this.setState({advLoading:false,advDone:true}),1150); },
      adv_loading:s.advLoading, adv_done:s.advDone,
      adv_nodes:nodes, adv_edges:edges,
      adv_tools:[{label:'图谱节点',value:'47'},{label:'关系边',value:'86'},{label:'一级关系',value:'12'},{label:'司法风险',value:'4'}],
      adv_answer:[
        {text:'股权结构以恒瑞医药集团为控股股东（约 24.1%），下设多家全资 / 控股研发与生产子公司，并通过海外平台 Luzsana 承接国际化布局，整体股权清晰、控制权稳定。',bullet:false,style:'font-size:13.5px;line-height:1.75;color:var(--text-2);margin:0'},
        {text:'创新能力维度评分领先：发明专利与在研管线储备充足，研发人员规模与对外合作（License-out）活跃度构成核心壁垒。',bullet:true,style:'display:flex;gap:9px;font-size:13.5px;line-height:1.7;color:var(--text-2);margin:0'},
        {text:'潜在风险：海外子公司经营受汇率与监管环境影响，需关注跨境关联交易与商誉减值敞口。',bullet:true,style:'display:flex;gap:9px;font-size:13.5px;line-height:1.7;color:var(--text-2);margin:0'}
      ],
      adv_innovLabels:['发明专利','在研管线','研发人员','对外合作'],
      adv_innovSeries:[{name:'创新能力维度评分',color:'#6d28d9',values:[88,82,79,71]}]
    };
  }

  renderVals(){
    return Object.assign({}, this.shellVals(), this.todayVals(), this.chatVals(), this.compareVals(), this.researchVals(), this.whiteboxVals(), this.databaseVals(), this.timelineVals(), this.advancedVals());
  }
}
