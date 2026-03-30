const state = {
  companies: [],
  industries: [],
  years: [],
  stats: {},
  deepseekEnabled: false,
  history: [],
  lastWorkflowMarkdown: "",
  lastWorkflowTitle: "",
  lastWorkflowHtml: "",
  lastChatResult: null,
  lastChatQuestion: "",
  dashboard: null,
  databaseCatalog: null,
  databasePreview: null,
  databaseSelectedTable: "",
  databaseSearch: "",
  databaseCategory: "all",
  profile: null,
  compare: null,
  timeline: null,
  snapshots: [],
  showcaseSceneId: "enterprise-diagnosis",
  chatContext: { companyName: "", reportYear: "", macro: false, compareCompanies: [] },
  projectRevealTimers: [],
};
const stages = ["正在理解问题并匹配企业、年份与上下文", "正在检索财务数据、年报原文和宏观指标", "正在生成结论并整理可追溯证据"];
const CHAT_HISTORY_KEY = "pharma_ai_web_history_v1";
const SNAPSHOT_KEY = "pharma_ai_web_snapshots_v1";
const SHOWCASE_SCENES = [
  {
    id: "enterprise-diagnosis",
    title: "企业诊断",
    eyebrow: "Scene 01",
    description: "从公司 360 画像切入，快速展示财务趋势、风险、创新和股权结构的统一视图。",
    companyName: "ST生物",
    reportYear: "2023",
    tab: "profile",
    quickPrompt: "请总结ST生物2023年的经营质量、风险点和关注指标",
    bullets: ["先看 360 画像，再切到预警与时间轴", "强调结构化事实与原文证据可以联动", "适合开场建立作品整体能力"],
  },
  {
    id: "peer-compare",
    title: "双公司对比",
    eyebrow: "Scene 02",
    description: "用对比矩阵和同级行业排名展示系统不只会回答单公司，而是能做经营差异判断。",
    companyName: "华兰生物",
    compareCompanyName: "乐普医疗",
    reportYear: "2023",
    tab: "compare",
    quickPrompt: "对比华兰生物和乐普医疗2023年的经营差异",
    bullets: ["对比营收、利润、现金流、研发和风险", "强调同级行业排名与比较检索是联动的", "适合展示决策支持价值"],
  },
  {
    id: "macro-linkage",
    title: "宏观联动",
    eyebrow: "Scene 03",
    description: "把宏观卫生指标与公司经营表现放到同一屏，展示不是只会读年报。",
    companyName: "ST生物",
    reportYear: "2023",
    tab: "dashboard",
    quickPrompt: "结合2022到2024年医疗卫生机构变化，分析ST生物的经营环境",
    bullets: ["先看宏观联动卡片，再到问答页追问影响", "强调系统同时打通 company facts 与 macro facts", "适合展示行业视角"],
  },
  {
    id: "whitebox-trace",
    title: "白盒溯源",
    eyebrow: "Scene 04",
    description: "用可展开 SQL、RAG 证据和定位跳转解释答案来源，强化可信度和可追溯性。",
    companyName: "ST生物",
    reportYear: "2023",
    tab: "whitebox",
    quickPrompt: "请生成一份关于ST生物的可追溯摘要",
    bullets: ["强调不是黑盒输出，而是可查 SQL 与原文页码", "现场点击证据定位按钮更有说服力", "适合作为收尾场景"],
  },
  {
    id: "auto-report",
    title: "自动报告",
    eyebrow: "Scene 05",
    description: "一键生成 Markdown 报告，继续演示批量生成、导出和快照保存。",
    companyName: "ST生物",
    reportYear: "2023",
    tab: "workflow",
    quickPrompt: "请为 ST生物 生成经营质量与风险诊断报告",
    bullets: ["先展示单公司自动报告，再切到批量模式", "展示 Markdown 与 PDF 导出", "最后保存快照，形成完整交付链路"],
  },
];
const PROJECT_MODULES = [
  {
    title: "展示与交互层",
    path: "webapp/ + scripts/streamlit + deepinsight/apps/",
    body: "FastAPI 自建网页与 Streamlit 比赛入口并存，前者负责展示版网页，后者通过 scripts/streamlit 下的启动脚本进入多页演示与缓存加速入口。",
  },
  {
    title: "检索与分析层",
    path: "deepinsight/core/",
    body: "retriever.py 负责 SQL、RAG、路由与可选 DeepSeek 调用；agent_tools.py 负责股权、风险、创新高级分析工具。",
  },
  {
    title: "数据构建层",
    path: "deepinsight/dataops/",
    body: "deepinsight.dataops 下统一负责底库初始化、年报入库、宏观导入和图谱扩展构建，Final_md 与宏观 Excel 都从这里接入。",
  },
  {
    title: "演示与测试层",
    path: "deepinsight/demo/ + tests/",
    body: "deepinsight.demo.demo_cache 生成本地缓存 JSON，tests/ 用冒烟和单元测试校验数据库、问答、工作流和高级分析链路。",
  },
];

const PROJECT_RUNTIME_STEPS = [
  "浏览器通过 / 访问 FastAPI 页面，静态资源来自 webapp/static/。",
  "前端调用 /api/chat、/api/dashboard、/api/workflow、/api/advanced 等接口。",
  "后端在 deepinsight/core/retriever.py 中执行 SQL 检索、Chroma 检索和答案整合。",
  "高级分析调用 deepinsight/core/agent_tools.py，读取股权、风险、专利相关扩展表。",
  "数据底座来自 SQLite、Chroma、本地 Markdown 年报目录和宏观 Excel 导入结果。",
];

const PROJECT_HIGHLIGHTS = [
  "当前架构是单仓单体：FastAPI、Streamlit、SQLite、Chroma 和导入脚本都在同一个代码库内。",
  "问答主链路采用 SQL + RAG 混合检索，可在无 DeepSeek Key 时退化为本地证据驱动模式。",
  "高级分析链路的数据表已落在 SQLite 中，但图谱/风险/专利扩展当前主要由 graph_data_pipeline.py 生成模拟数据。",
  "README 中 FastAPI 网页和 Streamlit 入口同时存在；以代码为准，两个入口目前都可以运行，但体验和能力并不完全一致。",
];
const PROJECT_FACTS = [
  { label: "架构风格", value: "单仓单体", detail: "FastAPI 网页与 Streamlit 比赛入口并存" },
  { label: "核心存储", value: "SQLite + Chroma", detail: "结构化事实库与向量检索库组合" },
  { label: "数据入口", value: "Final_md + Excel", detail: "企业年报 Markdown 与宏观 Excel 导入" },
  { label: "AI 运行模式", value: "本地优先", detail: "DeepSeek 为可选增强，不是唯一依赖" },
];
const PROJECT_ISSUES = [
  "FastAPI 与 Streamlit 两套入口同时存在，页面能力和缓存策略不完全一致。",
  "webapp/main.py 承担了较多聚合查询逻辑，缺少独立 service 层。",
  "retriever.py 职责偏重，耦合了路由、SQL 生成、SQL 执行、向量检索与答案整合。",
  "高级分析扩展表虽然已经落库，但 graph_data_pipeline.py 当前主要写入模拟数据。",
  "白盒与演示缓存能力在不同入口中的接入方式存在差异。",
];
const PROJECT_RECOMMENDATIONS = [
  "把聚合查询和页面组装逻辑从 webapp/main.py 下沉到统一应用服务层。",
  "将 retriever.py 拆分为路由、SQL、RAG、答案组装四类模块。",
  "为股权、风险、专利扩展表补正式采集/导入链路，替代 mock 数据生成。",
  "统一 FastAPI 与 Streamlit 的演示缓存接入策略，避免双入口分叉。",
  "如果后续走线上部署，优先评估服务端数据库和独立向量服务。",
];
const PROJECT_ASSUMPTIONS = [
  "仓库中未发现 Docker、Kubernetes 或云部署编排文件，因此部署图按本地单机模式描述。",
  "FastAPI 是否将完全替代 Streamlit，当前代码无法确认。",
  "高级分析未来是否接真实外部数据源，当前仓库无法确认；现阶段可确认存在 mock 生成脚本。",
  "deepinsight.core.cache_tools 的语义缓存能力是否在主链路启用，当前无法完全确认。",
];
const DB_TABLE_LABELS = {
  dim_industry: "行业维表",
  dim_company: "公司维表",
  dim_document: "文档维表",
  dict_financial_indicator: "财务指标字典",
  fact_financial_report: "财务事实表",
  dict_macro_indicator: "宏观指标字典",
  fact_macro_data: "宏观事实表",
  map_vector_chunk: "向量切片映射表",
  dim_party: "主体维表",
  dim_person: "自然人维表",
  fact_investment_relation: "投资关系表",
  fact_legal_risk: "司法风险表",
  fact_ip_patent: "专利事实表",
  smoke_test: "冒烟测试表",
};
const DB_COLUMN_LABELS = {
  id: "主键编号",
  industry_id: "行业编号",
  industry_name: "行业名称",
  industry_level: "行业层级",
  parent_industry_id: "上级行业编号",
  company_id: "公司编号",
  company_name: "公司名称",
  stock_code: "股票代码",
  primary_industry_id: "主行业编号",
  document_id: "文档编号",
  title: "标题",
  file_name: "文件名",
  file_path: "文件路径",
  file_hash: "文件哈希",
  report_year: "报告年份",
  is_latest: "是否最新",
  metadata_json: "元数据",
  updated_at: "更新时间",
  indicator_id: "指标编号",
  indicator_code: "指标代码",
  indicator_name: "指标名称",
  statement_category: "报表分类",
  value_type: "取值类型",
  default_unit: "默认单位",
  aliases: "别名",
  created_at: "创建时间",
  report_fact_id: "财务事实编号",
  period_label: "期间标签",
  value_role: "取值角色",
  value_num: "数值",
  source_page: "来源页码",
  macro_indicator_id: "宏观指标编号",
  period_date: "期间日期",
  region_name: "地区名称",
  macro_fact_id: "宏观事实编号",
  map_id: "映射编号",
  vector_id: "向量编号",
  chunk_index: "切片序号",
  page_start: "起始页码",
  chunk_hash: "切片哈希",
  party_id: "主体编号",
  party_type: "主体类型",
  person_id: "自然人编号",
  relation_id: "关系编号",
  investor_party_id: "投资方主体编号",
  investee_company_id: "被投公司编号",
  equity_ratio: "持股比例",
  source_type: "来源类型",
  batch_tag: "批次标签",
  risk_id: "风险编号",
  case_no: "案号",
  risk_type: "风险类型",
  filing_date: "立案日期",
  amount_involved: "涉案金额",
  severity_score: "严重度评分",
  detail_text: "详情文本",
  patent_id: "专利编号",
  patent_no: "专利号",
  application_no: "申请号",
  patent_name: "专利名称",
  patent_type: "专利类型",
  application_year: "申请年份",
  patent_score: "专利评分",
};
const ARCHITECTURE_REFERENCE_LABELS = {
  "webapp/main.py": "网页服务入口",
  "deepinsight/core/retriever.py": "问答检索核心",
  "deepinsight/core/agent_tools.py": "高级分析引擎",
  "deepinsight/dataops/": "数据构建脚本目录",
  "deepinsight/apps/": "Streamlit 页面目录",
  "webapp/main.py:/api/chat": "企业问答接口",
  "deepinsight/core/retriever.py:answer_query": "问答主流程函数",
  "deepinsight/dataops/db_init.py": "数据库初始化脚本",
  "deepinsight/dataops/db_expand.py": "扩展分析表脚本",
  Makefile: "本地启动脚本",
  "scripts/streamlit/system_console.py": "比赛版入口页面",
};
const DB_CATEGORY_META = {
  all: { label: "全部表", desc: "完整查看当前 SQLite 业务库中的所有表。", accent: "blue" },
  dimension: { label: "维度与主数据", desc: "企业、行业、文档等主数据表。", accent: "teal" },
  dictionary: { label: "指标字典", desc: "财务与宏观指标字典、字段标准。", accent: "cyan" },
  business: { label: "经营事实", desc: "财务事实和宏观事实等核心业务数据。", accent: "amber" },
  analysis: { label: "扩展分析", desc: "股权、司法风险、专利等扩展分析表。", accent: "rose" },
  vector: { label: "向量映射", desc: "文档切片与向量检索映射关系。", accent: "blue" },
  other: { label: "其他", desc: "测试表或暂未归类的数据表。", accent: "teal" },
};
const PROJECT_DIAGRAMS = [
  {
    key: "context",
    title: "系统上下文图",
    summary: "展示用户、双入口、核心服务、存储与外部依赖之间的真实交互关系。",
    mermaid: `flowchart LR
    User["评委/分析师/业务用户"] --> Browser["浏览器"]
    User --> StreamlitUI["Streamlit 页面入口\\nscripts/streamlit/system_console.py / chat_console.py / analysis_studio.py / report_studio.py"]
    Browser --> FastAPI["FastAPI 网页服务\\nwebapp/main.py"]
    FastAPI --> Retriever["检索分析核心\\ncore/retriever.py"]
    FastAPI --> AgentTools["高级分析工具\\ncore/agent_tools.py"]
    StreamlitUI --> Retriever
    StreamlitUI --> AgentTools
    StreamlitUI --> DemoCache["演示缓存\\ndemo_cache/*.json"]
    Retriever --> SQLite["SQLite\\ndata/enterprise_analysis.db"]
    Retriever --> Chroma["Chroma\\ndata/chroma/"]
    AgentTools --> SQLite
    DataPipeline["数据入库脚本\\ndeepinsight.dataops.*"] --> SQLite
    DataPipeline --> Chroma
    FinalMD["企业年报 Markdown\\nFinal_md/"] --> DataPipeline
    MacroExcel["宏观 Excel\\ndata/raw_macro/"] --> DataPipeline
    DeepSeek["DeepSeek API\\n可选"] -.->|增强| Retriever
    DeepSeek -.->|增强| AgentTools
    DeepSeek -.->|增强| StreamlitUI`,
    references: ["webapp/main.py", "deepinsight/core/retriever.py", "deepinsight/core/agent_tools.py", "deepinsight/dataops/"],
    strengths: ["单仓闭环完整，便于本地演示和快速迭代。", "没有外部复杂依赖时仍可本地跑通核心能力。"],
    risks: ["双入口并存导致维护分叉风险。", "DeepSeek 缺失时体验会退化。"],
  },
  {
    key: "layers",
    title: "模块 / 分层架构图",
    summary: "按展示层、应用层、核心分析层、数据构建层和存储层梳理代码结构。",
    displayMode: "preview",
    mermaid: `flowchart TB
    subgraph Presentation["展示与交互层"]
        Web["FastAPI + 静态前端\\nwebapp/main.py\\nwebapp/static/"]
        St["Streamlit 多页面\\nscripts/streamlit/system_console.py\\nscripts/streamlit/chat_console.py\\nscripts/streamlit/analysis_studio.py\\nscripts/streamlit/report_studio.py"]
    end
    subgraph Application["应用服务层"]
        ChatSvc["问答接口\\n/api/chat"]
        DashSvc["看板接口\\n/api/dashboard /profile /compare /timeline"]
        WorkflowSvc["报告接口\\n/api/workflow\\n/api/batch-workflow"]
        AdvancedSvc["高级分析接口\\n/api/advanced"]
        WhiteboxSvc["白盒接口\\n/api/whitebox"]
    end
    subgraph Domain["核心分析层"]
        Retriever["retriever.py\\nroute_question / generate_sql / retrieve_chunks / answer_query"]
        Tools["agent_tools.py\\ntool_get_equity_penetration / tool_get_risk_radar / tool_get_innovation_index"]
        Industry["industry_taxonomy.py\\ninfer_industry_name"]
        Cache["deepinsight.demo.demo_cache\\nbuild_*_cache / get_*_cache"]
    end
    subgraph DataOps["数据构建层"]
        Init["deepinsight.dataops.db_init\\n初始化 SQLite + Chroma"]
        Expand["deepinsight.dataops.db_expand\\n扩展图谱/风险/专利表"]
        Pipeline["deepinsight.dataops.data_pipeline\\n导入年报、抽取 facts、写入 chunks"]
        Macro["deepinsight.dataops.macro_import\\n导入 fact_macro_data"]
        Graph["deepinsight.dataops.graph_data_pipeline\\n生成股权/风险/专利模拟数据"]
    end
    subgraph Storage["存储层"]
        Sqlite["SQLite\\nenterprise_analysis.db"]
        Vector["Chroma\\nenterprise_documents"]
        Files["本地文件\\nFinal_md/\\ndemo_cache/\\ndata/raw_macro/"]
    end
    Web --> ChatSvc
    Web --> DashSvc
    Web --> WorkflowSvc
    Web --> AdvancedSvc
    Web --> WhiteboxSvc
    St --> Retriever
    St --> Tools
    St --> Cache
    ChatSvc --> Retriever
    DashSvc --> Retriever
    DashSvc --> Tools
    DashSvc --> Industry
    WorkflowSvc --> Retriever
    AdvancedSvc --> Tools
    Retriever --> Sqlite
    Retriever --> Vector
    Tools --> Sqlite
    Cache --> Files
    Init --> Sqlite
    Init --> Vector
    Expand --> Sqlite
    Pipeline --> Sqlite
    Pipeline --> Vector
    Pipeline --> Files
    Macro --> Sqlite
    Macro --> Files
    Graph --> Sqlite`,
    references: ["webapp/main.py", "deepinsight/core/", "deepinsight/dataops/", "deepinsight/apps/"],
    strengths: ["core 与 dataops 的边界相对清晰。", "同一套核心能力可被两个展示入口复用。"],
    risks: ["webapp/main.py 自身聚合逻辑较多。", "缺少 service/repository 层。"],
  },
  {
    key: "sequence",
    title: "核心业务时序图",
    summary: "以企业问答为例，展示 SQL、RAG 和可选 DeepSeek 如何在一次请求内协作。",
    displayMode: "preview",
    mermaid: `sequenceDiagram
    participant U as 用户
    participant B as 浏览器
    participant F as "FastAPI /api/chat"
    participant R as "core/retriever.py"
    participant S as SQLite
    participant C as Chroma
    participant D as "DeepSeek(可选)"
    U->>B: 输入企业问题
    B->>F: POST /api/chat
    F->>R: answer_query(question, filters, top_k, client)
    R->>R: route_question()
    alt 命中 SQL 或 hybrid
        R->>R: generate_sql() / sanitize_sql()
        R->>S: execute_sql()
        S-->>R: sql_rows
    end
    alt 命中 vector 或 hybrid
        R->>R: resolve_local_query_filters()
        R->>C: retrieve_chunks()
        C-->>R: chunks
    end
    alt 配置了 DEEPSEEK_API_KEY
        R->>D: 生成最终回答
        D-->>R: answer_markdown
    else 未配置 Key
        R->>R: 本地规则式摘要与证据拼装
    end
    R-->>F: answer_markdown / sources / sql / chunks / chart_spec
    F-->>B: JSON 响应
    B->>B: app.js 渲染卡片、图表、证据定位`,
    references: ["webapp/main.py:/api/chat", "deepinsight/core/retriever.py:answer_query"],
    strengths: ["支持降级运行。", "结构化数据与原文证据可以一起返回。"],
    risks: ["retriever.py 单文件职责偏重。", "SQL 与 RAG 路由策略目前集中在一个模块。"],
  },
  {
    key: "er",
    title: "数据模型 / ER 图",
    summary: "展示主链路表、向量映射表和高级分析扩展表之间的关系。",
    displayMode: "preview",
    mermaid: `erDiagram
    dim_industry ||--o{ dim_company : classifies
    dim_company ||--o{ dim_document : owns
    dict_financial_indicator ||--o{ fact_financial_report : defines
    dim_document ||--o{ fact_financial_report : contains
    dim_document ||--o{ map_vector_chunk : maps
    dict_macro_indicator ||--o{ fact_macro_data : defines
    dim_company ||--o| dim_party : maps_to_company_party
    dim_person ||--o| dim_party : maps_to_person_party
    dim_party ||--o{ fact_investment_relation : invests
    dim_company ||--o{ fact_investment_relation : investee
    dim_company ||--o{ fact_legal_risk : has
    dim_company ||--o{ fact_ip_patent : owns

    dim_industry {
        int industry_id PK
        text industry_name
        int industry_level
        int parent_industry_id
    }
    dim_company {
        int company_id PK
        text stock_code
        text company_name
        int primary_industry_id FK
    }
    dim_document {
        int document_id PK
        int company_id FK
        int report_year
        text file_path
        text file_hash
        int is_latest
        text metadata_json
    }
    fact_financial_report {
        int report_fact_id PK
        int document_id FK
        int indicator_id FK
        text period_label
        text value_role
        real value_num
        int source_page
    }
    map_vector_chunk {
        int map_id PK
        text vector_id
        int document_id FK
        int chunk_index
        int page_start
        text chunk_hash
    }
    dict_macro_indicator {
        int macro_indicator_id PK
        text indicator_code
        text indicator_name
    }
    fact_macro_data {
        int macro_fact_id PK
        int macro_indicator_id FK
        text period_date
        text region_name
        real value_num
    }
    dim_party {
        int party_id PK
        text party_type
        int company_id FK
        int person_id FK
    }
    fact_investment_relation {
        int relation_id PK
        int investor_party_id FK
        int investee_company_id FK
        real equity_ratio
        text source_type
        text batch_tag
    }
    fact_legal_risk {
        int risk_id PK
        int company_id FK
        text risk_type
        text filing_date
        real amount_involved
        int severity_score
        text source_type
    }
    fact_ip_patent {
        int patent_id PK
        int company_id FK
        text patent_name
        text patent_type
        int application_year
        real patent_score
        text source_type
    }`,
    references: ["deepinsight/dataops/db_init.py", "deepinsight/dataops/db_expand.py"],
    strengths: ["财务问答、宏观联动、图谱分析都有明确落库对象。", "文档和向量块映射表支持溯源。"],
    risks: ["metadata_json 承担部分半结构化信息。", "扩展表数据来源链路仍待强化。"],
  },
  {
    key: "deployment",
    title: "部署架构图",
    summary: "基于当前 Makefile、README 和入口代码，还原本地单机运行形态。",
    displayMode: "preview",
    mermaid: `flowchart TB
    subgraph Client["客户端"]
        Browser["浏览器"]
        StreamlitUser["Streamlit 访问者"]
    end
    subgraph Host["单机运行节点"]
        Uvicorn["uvicorn webapp.main:app"]
        Streamlit["streamlit run scripts/streamlit/system_console.py"]
        Static["webapp/static/"]
        FastAPI["webapp/main.py"]
        Core["deepinsight/core/"]
        DataOps["deepinsight/dataops/"]
        SQLite["data/enterprise_analysis.db"]
        Chroma["data/chroma/"]
        FinalMD["Final_md/"]
        DemoCache["demo_cache/"]
        MacroFile["data/raw_macro/"]
    end
    Browser --> Uvicorn
    Uvicorn --> FastAPI
    FastAPI --> Static
    FastAPI --> Core
    Core --> SQLite
    Core --> Chroma
    StreamlitUser --> Streamlit
    Streamlit --> Core
    Streamlit --> DemoCache
    DataOps --> SQLite
    DataOps --> Chroma
    FinalMD --> DataOps
    MacroFile --> DataOps`,
    references: ["Makefile", "webapp/main.py", "scripts/streamlit/system_console.py"],
    strengths: ["部署门槛低，适合答辩和录屏。", "运行链路清晰，依赖基本都在本机。"],
    risks: ["仓库中未见容器化或反向代理编排。", "SQLite + 本地 Chroma 不适合高并发生产场景。"],
  },
];
let mermaidBootstrapped = false;

function $(id) { return document.getElementById(id); }

function escapeHtml(value = "") {
  return value.replaceAll("&", "&amp;").replaceAll("<", "&lt;").replaceAll(">", "&gt;").replaceAll('"', "&quot;");
}

function escapeAttr(value = "") {
  return escapeHtml(String(value)).replaceAll("'", "&#39;");
}

function slugify(value = "") {
  return String(value).toLowerCase().replace(/[^a-z0-9\u4e00-\u9fff]+/g, "-").replace(/^-+|-+$/g, "").slice(0, 80) || "item";
}

function titleCaseEnglish(value = "") {
  return String(value)
    .split(/[_\s]+/)
    .filter(Boolean)
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}

function inferChineseLabelFromKey(key = "") {
  const tokenLabels = {
    dim: "维度",
    dict: "字典",
    fact: "事实",
    map: "映射",
    company: "公司",
    industry: "行业",
    document: "文档",
    indicator: "指标",
    macro: "宏观",
    financial: "财务",
    report: "报告",
    vector: "向量",
    chunk: "切片",
    party: "主体",
    person: "自然人",
    investment: "投资",
    relation: "关系",
    legal: "司法",
    risk: "风险",
    patent: "专利",
    stock: "股票",
    code: "代码",
    name: "名称",
    level: "层级",
    parent: "上级",
    primary: "主",
    file: "文件",
    hash: "哈希",
    year: "年份",
    metadata: "元数据",
    updated: "更新时间",
    statement: "报表",
    category: "分类",
    value: "数值",
    type: "类型",
    unit: "单位",
    alias: "别名",
    created: "创建时间",
    period: "期间",
    role: "角色",
    source: "来源",
    page: "页码",
    region: "地区",
    date: "日期",
    start: "起始",
    investor: "投资方",
    investee: "被投方",
    equity: "股权比例",
    batch: "批次",
    case: "案号",
    filing: "立案",
    amount: "金额",
    involved: "涉案",
    severity: "严重度",
    detail: "详情",
    application: "申请",
    default: "默认",
    latest: "最新",
    current: "当前",
    smoke: "测试",
    test: "表",
  };
  const tokens = String(key).split("_").filter(Boolean);
  const translated = tokens.map((token) => tokenLabels[token] || "").filter(Boolean);
  return translated.join("") || "字段说明";
}

function getTableDisplay(tableName = "") {
  return {
    zh: DB_TABLE_LABELS[tableName] || `${inferChineseLabelFromKey(tableName)}表`,
    en: tableName,
  };
}

function getColumnDisplay(columnName = "") {
  return {
    zh: DB_COLUMN_LABELS[columnName] || inferChineseLabelFromKey(columnName),
    en: columnName,
  };
}

function getReferenceDisplay(reference = "") {
  return {
    zh: ARCHITECTURE_REFERENCE_LABELS[reference] || "相关模块",
    en: reference,
  };
}

function formatDatabaseType(type = "") {
  const normalized = String(type || "").toUpperCase();
  const typeLabels = {
    TEXT: "文本",
    INTEGER: "整数",
    REAL: "浮点数",
    BLOB: "二进制",
    NUMERIC: "数值",
  };
  return typeLabels[normalized] ? `${typeLabels[normalized]} · ${normalized}` : normalized || "文本 · TEXT";
}

function classifyDatabaseTable(tableName = "") {
  if (/^dim_(industry|company|document)/.test(tableName)) return "dimension";
  if (/^dict_/.test(tableName)) return "dictionary";
  if (tableName === "fact_financial_report" || tableName === "fact_macro_data") return "business";
  if (/^fact_(legal_risk|ip_patent|investment_relation)/.test(tableName) || /^dim_(party|person)$/.test(tableName)) return "analysis";
  if (/^map_/.test(tableName)) return "vector";
  return "other";
}

function matchesDatabaseSearch(table = {}, query = "") {
  const normalizedQuery = String(query || "").trim().toLowerCase();
  if (!normalizedQuery) return true;
  const tableDisplay = getTableDisplay(table.table_name || "");
  const haystack = [
    table.table_name || "",
    tableDisplay.zh,
    ...(table.columns || []).flatMap((column) => {
      const display = getColumnDisplay(column);
      return [column, display.zh];
    }),
  ].join(" ").toLowerCase();
  return haystack.includes(normalizedQuery);
}

function formatNowLabel() {
  const now = new Date();
  return now.toLocaleString("zh-CN", { hour12: false });
}

function formatCompactNumber(value) {
  const amount = Number(value);
  if (!Number.isFinite(amount)) return "-";
  const abs = Math.abs(amount);
  if (abs >= 100000000) return `${(amount / 100000000).toFixed(2)}亿元`;
  if (abs >= 10000) return `${(amount / 10000).toFixed(2)}万元`;
  return amount.toLocaleString("zh-CN", { maximumFractionDigits: 2 });
}

function buildFilename(prefix, extension = "md") {
  return `${slugify(prefix || "deepinsight-report")}.${extension}`;
}

function sanitizeUrl(url = "") {
  const trimmed = String(url).trim();
  if (!trimmed) return "";
  return /^(https?:\/\/|mailto:|\/|#)/i.test(trimmed) ? trimmed : "";
}

function renderInlineMarkdown(text = "") {
  const placeholders = [];
  let safe = escapeHtml(String(text));
  safe = safe.replace(/`([^`\n]+)`/g, (_, code) => {
    const token = `@@CODE${placeholders.length}@@`;
    placeholders.push(`<code>${code}</code>`);
    return token;
  });
  safe = safe.replace(/\[([^\]]+)\]\(([^)]+)\)/g, (_, label, href) => {
    const sanitized = sanitizeUrl(href);
    if (!sanitized) return label;
    return `<a href="${escapeAttr(sanitized)}" target="_blank" rel="noopener noreferrer">${label}</a>`;
  });
  safe = safe.replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");
  safe = safe.replace(/__([^_]+)__/g, "<strong>$1</strong>");
  safe = safe.replace(/(^|[\s(\u3000])\*([^*\n]+)\*(?=$|[\s)，。！？；：,.!?:;])/g, "$1<em>$2</em>");
  safe = safe.replace(/(^|[\s(\u3000])_([^_\n]+)_(?=$|[\s)，。！？；：,.!?:;])/g, "$1<em>$2</em>");
  placeholders.forEach((html, index) => {
    safe = safe.replace(`@@CODE${index}@@`, html);
  });
  return safe;
}

function isMarkdownTableSeparator(line = "") {
  return /^\s*\|?(?:\s*:?-{3,}:?\s*\|)+\s*:?-{3,}:?\s*\|?\s*$/.test(line);
}

function splitMarkdownTableRow(line = "") {
  return line.trim().replace(/^\|/, "").replace(/\|$/, "").split("|").map((cell) => cell.trim());
}

function renderMarkdownValue(markdown = "") {
  const text = String(markdown || "");
  if (!text.trim()) return "";
  return /(^|\n)\s*(#{1,6}\s|[-*]\s+|\d+\.\s+|>\s?|```|\|)/.test(text) ? renderMarkdown(text) : renderInlineMarkdown(text);
}

function renderMarkdown(markdown = "") {
  const lines = String(markdown || "").replace(/\r\n?/g, "\n").split("\n");
  const html = [];
  let index = 0;
  while (index < lines.length) {
    const current = lines[index];
    const trimmed = current.trim();
    if (!trimmed) {
      index += 1;
      continue;
    }
    if (/^```/.test(trimmed)) {
      const language = trimmed.slice(3).trim();
      const code = [];
      index += 1;
      while (index < lines.length && !/^```/.test(lines[index].trim())) {
        code.push(lines[index]);
        index += 1;
      }
      if (index < lines.length) index += 1;
      html.push(`<pre><code${language ? ` data-lang="${escapeAttr(language)}"` : ""}>${escapeHtml(code.join("\n"))}</code></pre>`);
      continue;
    }
    if (/^#{1,4}\s+/.test(trimmed)) {
      const level = Math.min((trimmed.match(/^#{1,4}/) || ["#"])[0].length, 4);
      html.push(`<h${level}>${renderInlineMarkdown(trimmed.slice(level).trim())}</h${level}>`);
      index += 1;
      continue;
    }
    if (/^>\s?/.test(trimmed)) {
      const quoteLines = [];
      while (index < lines.length && /^>\s?/.test(lines[index].trim())) {
        quoteLines.push(lines[index].trim().replace(/^>\s?/, ""));
        index += 1;
      }
      html.push(`<blockquote>${quoteLines.map((line) => renderInlineMarkdown(line)).join("<br>")}</blockquote>`);
      continue;
    }
    if (index + 1 < lines.length && current.includes("|") && isMarkdownTableSeparator(lines[index + 1])) {
      const headers = splitMarkdownTableRow(current);
      const rows = [];
      index += 2;
      while (index < lines.length && lines[index].trim() && lines[index].includes("|")) {
        rows.push(splitMarkdownTableRow(lines[index]));
        index += 1;
      }
      html.push(`
        <div class="markdown-table-wrap">
          <table>
            <thead><tr>${headers.map((cell) => `<th>${renderInlineMarkdown(cell)}</th>`).join("")}</tr></thead>
            <tbody>
              ${rows.map((row) => `<tr>${headers.map((_, cellIndex) => `<td>${renderInlineMarkdown(row[cellIndex] || "")}</td>`).join("")}</tr>`).join("")}
            </tbody>
          </table>
        </div>
      `);
      continue;
    }
    if (/^[-*]\s+/.test(trimmed) || /^\d+\.\s+/.test(trimmed)) {
      const ordered = /^\d+\.\s+/.test(trimmed);
      const items = [];
      while (index < lines.length) {
        const listLine = lines[index].trim();
        if (!listLine) break;
        if (ordered && !/^\d+\.\s+/.test(listLine)) break;
        if (!ordered && !/^[-*]\s+/.test(listLine)) break;
        items.push(renderInlineMarkdown(listLine.replace(ordered ? /^\d+\.\s+/ : /^[-*]\s+/, "")));
        index += 1;
      }
      html.push(`<${ordered ? "ol" : "ul"}>${items.map((item) => `<li>${item}</li>`).join("")}</${ordered ? "ol" : "ul"}>`);
      continue;
    }
    const paragraph = [];
    while (index < lines.length) {
      const paragraphLine = lines[index];
      const paragraphTrimmed = paragraphLine.trim();
      if (!paragraphTrimmed) break;
      if (
        /^```/.test(paragraphTrimmed)
        || /^#{1,4}\s+/.test(paragraphTrimmed)
        || /^>\s?/.test(paragraphTrimmed)
        || /^[-*]\s+/.test(paragraphTrimmed)
        || /^\d+\.\s+/.test(paragraphTrimmed)
        || (index + 1 < lines.length && paragraphLine.includes("|") && isMarkdownTableSeparator(lines[index + 1]))
      ) {
        break;
      }
      paragraph.push(paragraphTrimmed);
      index += 1;
    }
    html.push(`<p>${paragraph.map((line) => renderInlineMarkdown(line)).join("<br>")}</p>`);
  }
  return html.join("");
}

function extractSection(markdown, title) {
  const match = markdown.match(new RegExp(`### ${title}\\n([\\s\\S]+?)(?:\\n### |$)`));
  return match ? match[1].trim() : "";
}

function extractSummary(markdown) {
  const text = extractSection(markdown, "摘要判断") || extractSection(markdown, "快速结论");
  return text ? text.split("\n").slice(0, 3).join("；").replaceAll("- ", "") : "";
}

function extractMetricCards(markdown) {
  const text = extractSection(markdown, "关键指标");
  if (!text) return [];
  return text.split("\n").filter((line) => line.trim().startsWith("- ")).slice(0, 4).map((line) => {
    const content = line.trim().slice(2);
    const parts = content.split("：");
    return { label: parts[0] || "指标", value: parts.slice(1).join("：") || "已命中指标" };
  });
}

function buildChips(result, question) {
  const chips = [];
  const push = (value) => { if (value && !chips.includes(value)) chips.push(value); };
  [...question.matchAll(/20\d{2}/g)].slice(0, 2).forEach((item) => push(`${item[0]}年`));
  (result.sql_rows || []).forEach((row) => push(row.company_name));
  if ((result.macro_rows || []).length) push("宏观联动");
  if (result.route === "hybrid") push("双库协同");
  if (result.route === "sql") push("结构化检索");
  if (result.route === "vector") push("向量检索");
  return chips.slice(0, 6);
}

function inferChatContext(question, result) {
  const context = { ...state.chatContext };
  const explicitCompany = $("companySelect").value || "";
  const explicitYear = $("yearSelect").value || "";
  const companyMatches = [...new Set((result.sql_rows || []).map((row) => row.company_name).filter(Boolean))];
  if (explicitCompany) context.companyName = explicitCompany;
  else if (companyMatches.length) context.companyName = companyMatches[0];
  if (explicitYear) context.reportYear = explicitYear;
  else {
    const matchedYear = question.match(/20\d{2}/);
    if (matchedYear) context.reportYear = matchedYear[0];
  }
  context.macro = Boolean((result.macro_rows || []).length) || /宏观|卫生|环境|影响/.test(question);
  context.compareCompanies = companyMatches.slice(0, 2);
  state.chatContext = context;
}

function enrichFollowupQuestion(question) {
  const trimmed = question.trim();
  if (!trimmed) return trimmed;
  const context = state.chatContext;
  const shortFollowup = /^(继续|再|那|并且|同时|顺便)/.test(trimmed);
  let enriched = trimmed;
  if (shortFollowup && context.companyName && !enriched.includes(context.companyName)) {
    enriched = `基于${context.companyName}${context.reportYear ? `${context.reportYear}年` : ""}，${enriched}`;
  }
  if (context.compareCompanies.length >= 2 && /继续对比|再对比|差异|谁更|哪个更/.test(enriched) && !context.compareCompanies.some((name) => enriched.includes(name))) {
    enriched = `对比${context.compareCompanies.join("、")}，${enriched}`;
  }
  if (context.macro && /环境|影响|结合|那/.test(enriched) && !enriched.includes("宏观")) {
    enriched = `${enriched}，并结合宏观卫生数据`;
  }
  return enriched;
}

function buildFollowups(result) {
  const prompts = [];
  const company = state.chatContext.companyName || "该公司";
  if ((state.chatContext.compareCompanies || []).length >= 2) {
    prompts.push(`继续对比${state.chatContext.compareCompanies.join("、")}的经营差异`);
  }
  if ((result.macro_rows || []).length || state.chatContext.macro) {
    prompts.push(`把这些宏观变化和${company}的经营表现结合起来分析`);
  }
  if ((result.sql_rows || []).length) {
    prompts.push(`把${company}的关键财务指标按趋势重新总结一遍`);
  }
  if ((result.chunks || []).length) {
    prompts.push(`从年报原文里继续追问${company}的主要风险点`);
  }
  prompts.push(`请生成一份关于${company}的可追溯摘要`);
  return [...new Set(prompts)].slice(0, 4);
}

function renderFollowups(prompts = []) {
  const host = $("chatFollowups");
  if (!host) return;
  if (!prompts.length) {
    host.innerHTML = "";
    return;
  }
  host.innerHTML = prompts.map((prompt) => `<button class="followup-button" type="button" data-followup="${escapeAttr(prompt)}">${escapeHtml(prompt)}</button>`).join("");
  host.querySelectorAll("[data-followup]").forEach((button) => {
    button.addEventListener("click", async () => {
      $("chatInput").value = button.dataset.followup || "";
      await handleChatSubmit($("chatInput").value);
    });
  });
}

function renderMetricGrid(cards) {
  if (!cards.length) return "";
  return `<div class="metric-grid">${cards.map((card) => `<div class="metric-card"><div class="label">${escapeHtml(card.label)}</div><div class="value">${escapeHtml(card.value)}</div></div>`).join("")}</div>`;
}

function renderSourceList(sources = []) {
  if (!sources.length) return "";
  return `<div class="source-list">${sources.map((source, index) => `
    <details class="source-item">
      <summary>
        <span class="source-index">${index + 1}</span>
        <span>${escapeHtml(source.label || "未知来源")}</span>
        <span style="margin-left:auto;display:inline-flex;gap:8px;align-items:center;">
          ${source.type === "vector" ? `<button class="mini-button" type="button" data-evidence-target="${escapeAttr(buildEvidenceId(source.label || "", `source-${index + 1}`))}">定位证据</button>` : ""}
          <span style="color:#64748b;font-size:0.82rem;">点击展开</span>
        </span>
      </summary>
      <div class="source-snippet">${escapeHtml(source.snippet || "暂无原文片段")}</div>
    </details>`).join("")}</div>`;
}

function renderSqlBlock(sql, title) {
  return sql ? `<div class="detail-block"><strong>${title}</strong><pre>${escapeHtml(sql)}</pre></div>` : "";
}

function renderTable(rows, title, maxRows = 10) {
  if (!rows || !rows.length) return "";
  const columns = Object.keys(rows[0]);
  const header = columns.map((col) => `<th>${escapeHtml(col)}</th>`).join("");
  const body = rows.slice(0, maxRows).map((row) => `<tr>${columns.map((col) => `<td title="${escapeHtml(String(row[col] ?? ""))}">${escapeHtml(String(row[col] ?? ""))}</td>`).join("")}</tr>`).join("");
  return `<div class="table-box"><strong>${title}</strong><div style="overflow:auto;"><table><thead><tr>${header}</tr></thead><tbody>${body}</tbody></table></div></div>`;
}

function renderChart(chartSpec) {
  if (!chartSpec || !chartSpec.rows || !chartSpec.rows.length) return "";
  return `
    <div class="chart-box">
      <strong>${escapeHtml(chartSpec.title || "图表洞察")}</strong>
      <div class="chart-host" data-echart='${escapeAttr(JSON.stringify({ kind: "chart_spec", payload: chartSpec }))}'></div>
    </div>
  `;
}

function renderImportOverview(data = {}) {
  const cards = data.cards || [];
  const healthCards = data.health_cards || [];
  const sourceRows = data.source_breakdown || [];
  const riskRows = data.risk_documents || [];
  return `
    <div class="panel dashboard-panel">
      <div class="section-header">
        <div>
          <div class="eyebrow">导入结果看板</div>
          <h3>入库覆盖与健康度</h3>
        </div>
        <div class="section-meta">${escapeHtml(data.last_import_at || "暂无最近导入时间")}</div>
      </div>
      <div class="dashboard-cards">
        ${cards.map((card) => `<div class="dashboard-card ${escapeHtml(card.accent || "")}"><div class="label">${escapeHtml(card.label)}</div><div class="value">${escapeHtml(String(card.value ?? "-"))}</div></div>`).join("")}
      </div>
      <div class="dashboard-cards compact">
        ${healthCards.map((card) => `<div class="dashboard-card subtle ${escapeHtml(card.accent || "")}"><div class="label">${escapeHtml(card.label)}</div><div class="value">${escapeHtml(String(card.value ?? "-"))}</div></div>`).join("")}
      </div>
      ${renderTable(sourceRows, "来源目录分布")}
      ${riskRows.length ? renderTable(riskRows, "空文本风险文档明细") : ""}
    </div>
  `;
}

function renderTrendOverview(data = {}) {
  if (!data.company_name) {
    return `<div class="panel dashboard-panel"><p>暂无可展示的趋势数据。</p></div>`;
  }
  const cards = data.cards || [];
  const anomalies = data.anomalies || [];
  const summary = data.summary || "";
  return `
    <div class="panel dashboard-panel">
      <div class="section-header">
        <div>
          <div class="eyebrow">财务指标趋势卡</div>
          <h3>${escapeHtml(data.company_name)} 近年经营趋势</h3>
        </div>
        <div class="section-meta">${escapeHtml((data.years || []).join(" / "))}</div>
      </div>
      <div class="dashboard-cards">
        ${cards.map((card) => `
          <div class="dashboard-card">
            <div class="status-row">
              <div class="label">${escapeHtml(card.label)}</div>
              <span class="status-dot ${escapeHtml((card.status || {}).level || "neutral")}">${escapeHtml((card.status || {}).label || "观察")}</span>
            </div>
            <div class="value">${escapeHtml(String(card.value ?? "-"))}${escapeHtml(card.unit || "")}</div>
            <div class="card-meta">${escapeHtml(String(card.report_year || "-"))} 年 · ${escapeHtml(card.change_text || "同比待补充")}</div>
          </div>
        `).join("")}
      </div>
      ${summary ? `<div class="summary-card"><div class="label">自动摘要</div><div class="value">${renderMarkdownValue(summary)}</div></div>` : ""}
      ${anomalies.length ? `<div class="summary-card trend-alerts"><div class="label">异常提示</div><ul>${anomalies.map((item) => `<li>${renderInlineMarkdown(item)}</li>`).join("")}</ul></div>` : ""}
      ${renderChart(data.amount_chart)}
      ${renderChart(data.ratio_chart)}
    </div>
  `;
}

function renderRankingOverview(data = {}) {
  if (!data.company_name) {
    return `<div class="panel dashboard-panel"><p>暂无可展示的行业排名数据。</p></div>`;
  }
  const boards = data.boards || [];
  return `
    <div class="panel dashboard-panel">
      <div class="section-header">
        <div>
          <div class="eyebrow">行业横向排名</div>
          <h3>${escapeHtml(data.company_name)} 在 ${escapeHtml(data.industry_name || "全部行业")} 的位置</h3>
        </div>
        <div class="section-meta">${escapeHtml(data.scope_label || "排名")} · ${escapeHtml(String(data.report_year || "-"))} 年</div>
      </div>
      <div class="ranking-grid">
        ${boards.map((board) => {
          const maxValue = Math.max(...(board.rows || []).map((item) => Math.abs(Number(item.value_num) || 0)), 1);
          return `
            <div class="ranking-card">
              <div class="ranking-head">
                <strong>${escapeHtml(board.indicator_name)}</strong>
                <span>${board.selected_company_rank ? `本公司第 ${board.selected_company_rank} 名 / ${board.sample_size} 家` : `样本 ${board.sample_size} 家`}</span>
              </div>
              <div class="simple-bars">
                ${(board.rows || []).map((row) => `
                  <div class="bar-row ${row.is_selected ? "selected" : ""}">
                    <div>#${escapeHtml(String(row.rank))} ${escapeHtml(row.company_name)}</div>
                    <div class="bar-track"><div class="bar-fill" style="width:${((Math.abs(Number(row.value_num) || 0) / maxValue) * 100).toFixed(2)}%;"></div></div>
                    <div>${escapeHtml(String(row.value_num ?? "-"))}${escapeHtml(row.unit || "")}</div>
                  </div>
                `).join("")}
              </div>
            </div>
          `;
        }).join("")}
      </div>
    </div>
  `;
}

function renderAlertOverview(data = {}) {
  const items = data.items || [];
  return `
    <div class="panel dashboard-panel">
      <div class="section-header">
        <div>
          <div class="eyebrow">预警中心</div>
          <h3>${escapeHtml(data.company_name || "全库")} 风险与异常信号</h3>
        </div>
        <div class="section-meta">${renderInlineMarkdown(data.summary || "暂无预警摘要")}</div>
      </div>
      <div class="dashboard-cards compact">
        ${(data.cards || []).map((card) => `<div class="dashboard-card ${escapeHtml(card.accent || "")}"><div class="label">${escapeHtml(card.label)}</div><div class="value">${escapeHtml(String(card.value ?? "-"))}</div></div>`).join("")}
      </div>
      ${items.length ? `
        <div class="alert-list">
          ${items.map((item) => `
            <div class="alert-item ${item.severity === "高" ? "high" : (item.severity === "中" ? "medium" : "low")}">
              <div class="alert-head">
                <strong>${escapeHtml(item.company_name || "未知公司")}</strong>
                <span class="status-dot ${item.severity === "高" ? "red" : (item.severity === "中" ? "amber" : "neutral")}">${escapeHtml(item.severity)}优先级</span>
              </div>
              <div class="card-meta">${escapeHtml(item.category || "预警")} · ${escapeHtml(String(item.report_year || "-"))}</div>
              <div class="value">${escapeHtml(item.signal || "已命中风险信号")}</div>
              <div class="card-meta">${escapeHtml(item.detail || "")}</div>
            </div>
          `).join("")}
        </div>
      ` : '<p>当前没有需要重点展示的预警。</p>'}
    </div>
  `;
}

function renderMacroOverview(data = {}) {
  if (!data.company_name) {
    return `<div class="panel dashboard-panel"><p>暂无可展示的宏观联动数据。</p></div>`;
  }
  return `
    <div class="panel dashboard-panel">
      <div class="section-header">
        <div>
          <div class="eyebrow">宏观联动</div>
          <h3>${escapeHtml(data.company_name)} 的外部环境信号</h3>
        </div>
        <div class="section-meta">宏观卫生指标与公司趋势联动</div>
      </div>
      <div class="dashboard-cards compact">
        ${(data.cards || []).map((card) => `<div class="dashboard-card ${escapeHtml(card.accent || "cyan")}"><div class="label">${escapeHtml(card.label)}</div><div class="value">${escapeHtml(String(card.value ?? "-"))}</div></div>`).join("")}
      </div>
      ${data.summary ? `<div class="summary-card"><div class="label">自动摘要</div><div class="value">${renderMarkdownValue(data.summary)}</div></div>` : ""}
      ${renderChart(data.revenue_chart)}
      ${renderChart(data.macro_chart)}
    </div>
  `;
}

function renderProfileOverview(data = {}) {
  if (!data.company_name) {
    return `<div class="panel dashboard-panel"><p>请选择企业后查看公司 360 画像。</p></div>`;
  }
  return `
    <div class="panel dashboard-panel">
      <div class="section-header">
        <div>
          <div class="eyebrow">公司 360 画像</div>
          <h3>${escapeHtml(data.company_name)} · ${escapeHtml(data.industry_name || "医药生物")}</h3>
        </div>
        <div class="section-meta">${escapeHtml(String(data.report_year || "-"))} 年</div>
      </div>
      <div class="dashboard-cards">
        ${(data.cards || []).map((card) => `<div class="dashboard-card ${escapeHtml(card.accent || "")}"><div class="label">${escapeHtml(card.label)}</div><div class="value">${escapeHtml(String(card.value ?? "-"))}</div></div>`).join("")}
      </div>
      ${data.summary ? `<div class="summary-card"><div class="label">画像摘要</div><div class="value">${renderMarkdownValue(data.summary)}</div></div>` : ""}
      <div class="dashboard-grid">
        <div class="panel dashboard-panel">
          <div class="section-header"><h3>财务快照</h3><div class="section-meta">关键指标</div></div>
          <div class="kv-grid">
            ${(data.metric_cards || []).map((card) => `<div class="kv-item"><strong>${escapeHtml(card.label)}</strong><div>${escapeHtml(card.value || "-")}</div><div class="card-meta">${escapeHtml(card.meta || "")}</div></div>`).join("")}
          </div>
        </div>
        <div class="panel dashboard-panel">
          <div class="section-header"><h3>风险与创新</h3><div class="section-meta">工具侧画像</div></div>
          <div class="kv-grid">
            ${(data.risk_cards || []).slice(0, 5).map((card) => `<div class="kv-item"><strong>${escapeHtml(card.label)}</strong><div>${escapeHtml(String(card.value ?? "-"))}</div></div>`).join("")}
            ${(data.innovation_cards || []).slice(0, 5).map((card) => `<div class="kv-item"><strong>${escapeHtml(card.label)}</strong><div>${escapeHtml(String(card.value ?? "-"))}</div></div>`).join("")}
          </div>
        </div>
      </div>
      ${(data.alerts || []).length ? `<div class="summary-card trend-alerts"><div class="label">画像预警</div><ul>${data.alerts.map((item) => `<li>${renderInlineMarkdown(item.signal)}：${renderInlineMarkdown(item.detail || "")}</li>`).join("")}</ul></div>` : ""}
      ${data.latest_document ? `<div class="summary-card"><div class="label">最新文档</div><div class="value">${escapeHtml(data.latest_document.file_name || "")}</div><div class="card-meta">${escapeHtml(data.latest_document.file_path || "")}</div></div>` : ""}
      ${renderChart(data.trend_chart)}
      ${renderChart(data.ratio_chart)}
      ${renderChart(data.innovation_chart)}
    </div>
  `;
}

function renderCompareOverview(data = {}) {
  if (!(data.company_names || []).length) {
    return `<div class="panel dashboard-panel"><p>请选择企业后查看对比矩阵。</p></div>`;
  }
  return `
    <div class="panel dashboard-panel">
      <div class="section-header">
        <div>
          <div class="eyebrow">对比矩阵</div>
          <h3>${escapeHtml((data.company_names || []).join(" vs "))}</h3>
        </div>
        <div class="section-meta">${escapeHtml(String(data.report_year || "-"))} 年</div>
      </div>
      ${data.summary ? `<div class="summary-card"><div class="label">自动摘要</div><div class="value">${renderMarkdownValue(data.summary)}</div></div>` : ""}
      ${renderTable(data.rows || [], "核心指标对比")}
      ${renderChart(data.chart)}
    </div>
  `;
}

function renderTimelineOverview(data = {}) {
  const events = data.events || [];
  if (!data.company_name) {
    return `<div class="panel dashboard-panel"><p>请选择企业后查看事件时间轴。</p></div>`;
  }
  return `
    <div class="panel dashboard-panel">
      <div class="section-header">
        <div>
          <div class="eyebrow">事件时间轴</div>
          <h3>${escapeHtml(data.company_name)} 的经营轨迹</h3>
        </div>
        <div class="section-meta">${renderInlineMarkdown(data.summary || "")}</div>
      </div>
      <div class="dashboard-cards compact">
        ${(data.cards || []).map((card) => `<div class="dashboard-card ${escapeHtml(card.accent || "")}"><div class="label">${escapeHtml(card.label)}</div><div class="value">${escapeHtml(String(card.value ?? "-"))}</div></div>`).join("")}
      </div>
      ${events.length ? `
        <div class="timeline-list">
          ${events.map((item) => `
            <div class="timeline-item">
              <div class="timeline-date">${escapeHtml(item.event_date || "-")}</div>
              <div class="timeline-dot ${item.category === "财务" ? "finance" : (item.category === "风险" ? "risk" : "innovation")}"></div>
              <div class="timeline-body">
                <strong>${escapeHtml(item.title || "事件")}</strong>
                <div class="card-meta">${escapeHtml(item.category || "事件分类")}</div>
                <div>${escapeHtml(item.detail || "")}</div>
              </div>
            </div>
          `).join("")}
        </div>
      ` : '<p>当前暂无时间轴事件。</p>'}
    </div>
  `;
}

function syncDatabaseTableSelect() {
  const select = $("databaseTableSelect");
  if (!select) return;
  const tables = state.databaseCatalog?.tables || [];
  if (!tables.length) {
    select.innerHTML = '<option value="">暂无数据表</option>';
    return;
  }
  select.innerHTML = tables.map((table) => {
    const tableDisplay = getTableDisplay(table.table_name);
    return `<option value="${escapeAttr(table.table_name)}">${escapeHtml(`${tableDisplay.zh} / ${tableDisplay.en}`)}</option>`;
  }).join("");
  select.value = state.databaseSelectedTable || tables[0].table_name;
}

function renderDatabaseCatalog(data = {}) {
  const tables = data.tables || [];
  if (!tables.length) {
    return `<div class="panel dashboard-panel"><p>当前没有可展示的数据表。</p></div>`;
  }
  const searchQuery = state.databaseSearch || "";
  const currentCategory = state.databaseCategory || "all";
  const filteredTables = tables.filter((table) => {
    const category = classifyDatabaseTable(table.table_name);
    if (currentCategory !== "all" && category !== currentCategory) return false;
    return matchesDatabaseSearch(table, searchQuery);
  });
  const groupedTables = Object.entries(DB_CATEGORY_META)
    .filter(([key]) => key !== "all")
    .map(([key, meta]) => ({
      key,
      meta,
      tables: filteredTables.filter((table) => classifyDatabaseTable(table.table_name) === key),
    }))
    .filter((group) => group.tables.length);
  const selectedDisplay = getTableDisplay(state.databaseSelectedTable || tables[0].table_name || "");
  const summaryCounts = Object.keys(DB_CATEGORY_META)
    .filter((key) => key !== "all")
    .map((key) => ({
      key,
      label: DB_CATEGORY_META[key].label,
      count: tables.filter((table) => classifyDatabaseTable(table.table_name) === key).length,
      accent: DB_CATEGORY_META[key].accent,
    }));
  return `
    <div class="panel dashboard-panel">
      <div class="section-header">
        <div>
          <div class="eyebrow">数据库目录</div>
          <h3>数据底座导航</h3>
        </div>
        <div class="section-meta">当前连接：本地 SQLite 业务库</div>
      </div>
      <div class="database-hero">
        <div>
          <div class="database-hero-title">中文名称用于展示讲解，英文名称保持与底层真实库表一致。</div>
          <div class="card-meta">适合在答辩里先讲“业务含义”，需要时再落回真实英文表名和字段名。</div>
        </div>
        <div class="database-hero-badge">SQLite Business Catalog</div>
      </div>
      <div class="dashboard-cards compact">
        <div class="dashboard-card blue"><div class="label">业务表数量</div><div class="value">${escapeHtml(String(data.table_count ?? tables.length))}</div></div>
        <div class="dashboard-card teal"><div class="label">当前选中</div><div class="value">${escapeHtml(selectedDisplay.zh)}</div><div class="card-meta">${escapeHtml(selectedDisplay.en)}</div></div>
        <div class="dashboard-card cyan"><div class="label">当前筛选</div><div class="value">${escapeHtml(DB_CATEGORY_META[currentCategory]?.label || "全部表")}</div><div class="card-meta">${escapeHtml(searchQuery ? `关键词：${searchQuery}` : "未输入关键词")}</div></div>
      </div>
      <div class="database-summary-strip">
        ${summaryCounts.map((item) => `<div class="database-summary-pill ${escapeHtml(item.accent)}"><span>${escapeHtml(item.label)}</span><strong>${escapeHtml(String(item.count))}</strong></div>`).join("")}
      </div>
      <div class="database-filter-bar">
        ${Object.entries(DB_CATEGORY_META).map(([key, meta]) => `
          <button
            type="button"
            class="database-filter-chip ${key === currentCategory ? "active" : ""}"
            data-database-category="${escapeAttr(key)}"
          >
            <span>${escapeHtml(meta.label)}</span>
            <em>${escapeHtml(key === "all" ? String(tables.length) : String(tables.filter((table) => classifyDatabaseTable(table.table_name) === key).length))}</em>
          </button>
        `).join("")}
      </div>
      ${filteredTables.length ? groupedTables.map((group) => `
        <div class="database-group">
          <div class="database-group-head">
            <div>
              <div class="database-group-title">${escapeHtml(group.meta.label)}</div>
              <div class="card-meta">${escapeHtml(group.meta.desc)}</div>
            </div>
            <div class="database-group-count">${escapeHtml(String(group.tables.length))} 张表</div>
          </div>
          <div class="database-catalog-grid">
            ${group.tables.map((table) => {
          const tableDisplay = getTableDisplay(table.table_name);
          const previewColumns = (table.columns || []).slice(0, 3);
          const restCount = Math.max((table.columns || []).length - previewColumns.length, 0);
          return `
          <button
            class="database-table-card ${table.table_name === state.databaseSelectedTable ? "active" : ""}"
            type="button"
            data-database-table="${escapeAttr(table.table_name)}"
          >
            <div class="database-table-name">${escapeHtml(tableDisplay.zh)}</div>
            <div class="database-table-en">${escapeHtml(tableDisplay.en)}</div>
            <div class="database-table-meta">行数 ${escapeHtml(String(table.row_count ?? 0))} · 字段 ${escapeHtml(String(table.column_count ?? 0))}</div>
            <div class="database-table-columns">
              ${previewColumns.map((column) => {
                const columnDisplay = getColumnDisplay(column);
                return `<span class="chip" title="${escapeAttr(columnDisplay.en)}">${escapeHtml(columnDisplay.zh)}</span>`;
              }).join("")}
              ${restCount ? `<span class="chip">+${restCount} 个字段</span>` : ""}
            </div>
          </button>
        `;
        }).join("")}
          </div>
        </div>
      `).join("") : `<div class="panel dashboard-panel"><p>当前筛选条件下没有匹配的数据表，可以换个关键词或分类再试。</p></div>`}
    </div>
  `;
}

function renderDatabaseRowsTable(rows = [], columns = [], title = "", limit = 20) {
  if (!rows.length || !columns.length) return "";
  const header = columns.map((column) => {
    const display = getColumnDisplay(column.name);
    return `
      <th>
        <div class="db-header-zh">${escapeHtml(display.zh)}</div>
        <div class="db-header-en">${escapeHtml(display.en)}</div>
      </th>
    `;
  }).join("");
  const body = rows.slice(0, limit).map((row) => `
    <tr>
      ${columns.map((column) => `<td title="${escapeHtml(String(row[column.name] ?? ""))}">${escapeHtml(String(row[column.name] ?? ""))}</td>`).join("")}
    </tr>
  `).join("");
  return `
    <div class="table-box">
      <strong>${escapeHtml(title)}</strong>
      <div class="card-meta">表头按“中文说明 / 英文字段名”双语展示，底层存储字段保持英文。</div>
      <div style="overflow:auto;">
        <table class="database-preview-table">
          <thead><tr>${header}</tr></thead>
          <tbody>${body}</tbody>
        </table>
      </div>
    </div>
  `;
}

function renderDatabasePreview(data = {}) {
  if (!data.table_name) {
    return `<div class="panel dashboard-panel"><p>请选择一个数据表后查看结构和示例数据。</p></div>`;
  }
  const columns = data.columns || [];
  const tableDisplay = getTableDisplay(data.table_name);
  const categoryMeta = DB_CATEGORY_META[classifyDatabaseTable(data.table_name)] || DB_CATEGORY_META.other;
  const schemaScrollId = `database-schema-strip-${slugify(data.table_name)}`;
  return `
    <div class="panel dashboard-panel database-preview-panel">
      <div class="section-header">
        <div>
          <div class="eyebrow">数据表预览</div>
          <h3>${escapeHtml(tableDisplay.zh)}</h3>
          <div class="card-meta">${escapeHtml(tableDisplay.en)}</div>
        </div>
        <div class="section-meta">前 ${escapeHtml(String(data.limit || 0))} 行预览</div>
      </div>
      <div class="database-preview-intro">
        <div>
          <div class="database-preview-title">${escapeHtml(categoryMeta.label)}</div>
          <div class="card-meta">${escapeHtml(categoryMeta.desc)}</div>
        </div>
        <div class="database-hero-badge">${escapeHtml(tableDisplay.en)}</div>
      </div>
      <div class="database-scroll-note">当前区域支持左右滑动，适合字段较多的字典表和宽表展示。</div>
      <div class="database-metrics-grid">
        <div class="dashboard-card blue"><div class="label">总行数</div><div class="value">${escapeHtml(String(data.row_count ?? 0))}</div></div>
        <div class="dashboard-card teal"><div class="label">字段数</div><div class="value">${escapeHtml(String(columns.length))}</div></div>
        <div class="dashboard-card cyan"><div class="label">预览行数</div><div class="value">${escapeHtml(String((data.rows || []).length))}</div></div>
      </div>
      <div class="database-strip-head">
        <div>
          <strong>字段滑动带</strong>
          <div class="card-meta">字段较多时请左右滑动查看完整字段定义，或点击箭头快速移动。</div>
        </div>
        <div class="database-strip-actions">
          <button class="mini-button" type="button" data-scroll-left="${escapeAttr(schemaScrollId)}">向左</button>
          <button class="mini-button" type="button" data-scroll-right="${escapeAttr(schemaScrollId)}">向右</button>
        </div>
      </div>
      <div class="database-scroll-shell database-scroll-shell-highlight" id="${escapeAttr(schemaScrollId)}">
        <div class="database-schema-row">
        ${columns.map((column) => `
          <div class="database-schema-card">
            <div class="database-schema-name">${escapeHtml(getColumnDisplay(column.name || "").zh)}</div>
            <div class="database-schema-en">${escapeHtml(column.name || "")}</div>
            <div class="database-schema-meta">${escapeHtml(formatDatabaseType(column.type || "TEXT"))}</div>
            <div class="database-schema-badges">
              ${column.is_pk ? '<span class="database-badge">主键 PK</span>' : ""}
              ${column.notnull ? '<span class="database-badge">非空 NOT NULL</span>' : ""}
              ${!column.notnull ? '<span class="database-badge subtle">可为空 NULL</span>' : ""}
            </div>
            ${column.default_value !== null && column.default_value !== undefined ? `<div class="card-meta">默认值 Default：${escapeHtml(String(column.default_value))}</div>` : ""}
          </div>
        `).join("")}
        </div>
      </div>
      ${renderDatabaseRowsTable(data.rows || [], columns, `示例数据（前 ${data.limit || 0} 行）`, data.limit || 20)}
      ${data.create_sql ? `
        <details class="detail-block database-sql-toggle">
          <summary>查看建表 SQL / Create Statement</summary>
          <pre>${escapeHtml(data.create_sql)}</pre>
        </details>
      ` : ""}
    </div>
  `;
}

function getShowcaseScene(sceneId = state.showcaseSceneId) {
  return SHOWCASE_SCENES.find((item) => item.id === sceneId) || SHOWCASE_SCENES[0];
}

function getShowcaseNarrative(scene) {
  if (!scene) return "当前场景说明待补充。";
  if (scene.id === "enterprise-diagnosis") {
    return state.profile?.summary || state.dashboard?.trend_overview?.summary || "公司画像会展示财务趋势、风险、创新和股权结构。";
  }
  if (scene.id === "peer-compare") {
    return state.compare?.summary || "对比矩阵会从核心财务指标、风险和创新三个方向做比较。";
  }
  if (scene.id === "macro-linkage") {
    return state.dashboard?.macro_overview?.summary || "宏观联动页面会展示医疗卫生指标与公司经营表现的联动关系。";
  }
  if (scene.id === "auto-report") {
    return state.lastWorkflowMarkdown ? extractSummary(state.lastWorkflowMarkdown) : "自动报告适合展示从检索到交付的完整链路。";
  }
  return "白盒溯源适合展示系统的可解释性和证据透明度。";
}

function renderShowcaseHero() {
  const stats = state.stats || {};
  const activeScene = getShowcaseScene();
  return `
    <div class="panel showcase-hero">
      <div class="showcase-head">
        <div>
          <div class="eyebrow">答辩展示模式</div>
          <h3>一页串起“数据入库 → 检索分析 → 可视化决策 → 白盒交付”完整链路</h3>
          <p class="hero-copy">这个模式更偏答辩和录屏演示。你可以按推荐顺序逐场景切换，也可以一键进入当前讲解重点。</p>
        </div>
        <div class="action-row">
          <button id="togglePresentationModeButton" class="ghost" type="button">切换大屏模式</button>
          <button id="toggleFullscreenButton" class="primary" type="button">全屏演示</button>
        </div>
      </div>
      <div class="dashboard-cards">
        <div class="dashboard-card blue"><div class="label">企业覆盖数</div><div class="value">${escapeHtml(String(stats.companies ?? "-"))}</div></div>
        <div class="dashboard-card teal"><div class="label">文档总量</div><div class="value">${escapeHtml(String(stats.documents ?? "-"))}</div></div>
        <div class="dashboard-card amber"><div class="label">财务事实数</div><div class="value">${escapeHtml(String(stats.financial_facts ?? "-"))}</div></div>
        <div class="dashboard-card cyan"><div class="label">宏观事实数</div><div class="value">${escapeHtml(String(stats.macro_facts ?? "-"))}</div></div>
      </div>
      <div class="showcase-current">
        <div class="summary-card">
          <div class="label">当前推荐场景</div>
          <div class="value">${escapeHtml(activeScene.title)}</div>
          <div class="card-meta">${escapeHtml(activeScene.description)}</div>
        </div>
        <div class="summary-card">
          <div class="label">推荐讲法</div>
          <div class="value">${escapeHtml(getShowcaseNarrative(activeScene))}</div>
        </div>
      </div>
    </div>
  `;
}

function renderShowcaseScenes() {
  const activeScene = getShowcaseScene();
  return `
    <div class="panel dashboard-panel">
      <div class="section-header">
        <div>
          <div class="eyebrow">场景剧本</div>
          <h3>推荐的 5 段演示顺序</h3>
        </div>
        <div class="section-meta">点击“进入场景”可直接切到对应页面</div>
      </div>
      <div class="showcase-scene-grid">
        ${SHOWCASE_SCENES.map((scene, index) => `
          <div class="scene-card ${scene.id === activeScene.id ? "active" : ""}">
            <div class="scene-index">${index + 1}</div>
            <div class="eyebrow">${escapeHtml(scene.eyebrow)}</div>
            <h4>${escapeHtml(scene.title)}</h4>
            <p>${escapeHtml(scene.description)}</p>
            <div class="chip-row">
              ${scene.companyName ? `<span class="chip">${escapeHtml(scene.companyName)}</span>` : ""}
              ${scene.reportYear ? `<span class="chip">${escapeHtml(scene.reportYear)}年</span>` : ""}
              <span class="chip">${escapeHtml(scene.tab)}</span>
            </div>
            <div class="action-row">
              <button class="primary" type="button" data-showcase-scene="${escapeAttr(scene.id)}">进入场景</button>
              <button class="ghost" type="button" data-showcase-run="${escapeAttr(scene.id)}">按推荐问题演示</button>
            </div>
          </div>
        `).join("")}
      </div>
    </div>
  `;
}

function renderShowcaseSpotlight() {
  const scene = getShowcaseScene();
  return `
    <div class="panel dashboard-panel">
      <div class="section-header">
        <div>
          <div class="eyebrow">当前场景话术</div>
          <h3>${escapeHtml(scene.title)} 应该怎么讲</h3>
        </div>
        <div class="section-meta">${escapeHtml(scene.companyName || "全局场景")} · ${escapeHtml(scene.reportYear || "-")}</div>
      </div>
      <div class="dashboard-grid">
        <div class="summary-card">
          <div class="label">一句话定位</div>
          <div class="value">${escapeHtml(scene.description)}</div>
        </div>
        <div class="summary-card">
          <div class="label">推荐问题</div>
          <div class="value">${escapeHtml(scene.quickPrompt || "无")}</div>
        </div>
      </div>
      <div class="showcase-bullets">
        ${(scene.bullets || []).map((item) => `<div class="kv-item">${escapeHtml(item)}</div>`).join("")}
      </div>
    </div>
  `;
}

function renderShowcaseFlow() {
  const flowItems = [
    { title: "数据入库", body: "递归导入 Final_md、抽取财务 facts、写入向量库，并自动识别坏文档。" },
    { title: "双库协同", body: "结构化 SQL + 非结构化 RAG 联合检索，支持单公司、对比和宏观联动。" },
    { title: "多维分析", body: "画像、排名、时间轴、风险雷达、创新指数和股权穿透统一展示。" },
    { title: "白盒交付", body: "答案可回看 SQL、原文片段、证据定位，并导出报告与保存快照。" },
  ];
  return `
    <div class="panel dashboard-panel">
      <div class="section-header">
        <div>
          <div class="eyebrow">技术闭环</div>
          <h3>作品不是单点能力，而是一条完整分析链路</h3>
        </div>
        <div class="section-meta">适合在答辩中解释系统结构</div>
      </div>
      <div class="showcase-flow">
        ${flowItems.map((item, index) => `
          <div class="flow-card">
            <div class="scene-index">${index + 1}</div>
            <strong>${escapeHtml(item.title)}</strong>
            <p>${escapeHtml(item.body)}</p>
          </div>
        `).join("")}
      </div>
    </div>
  `;
}

function renderShowcasePlaybook() {
  const steps = [
    "第 1 分钟：先从“公司 360 画像”开场，说明系统不是简单聊天，而是整合财务、风险、创新和图谱。",
    "第 2 分钟：切到“对比矩阵”，强调系统支持双公司经营差异判断与同业参考。",
    "第 3 分钟：切到“宏观联动”，展示公司分析不脱离医疗卫生外部环境。",
    "第 4 分钟：切到“白盒溯源”，现场点开 SQL 和原文证据，强化可信度。",
    "第 5 分钟：最后生成“自动报告”，展示 Markdown、PDF 和快照，形成交付闭环。",
  ];
  return `
    <div class="panel dashboard-panel">
      <div class="section-header">
        <div>
          <div class="eyebrow">答辩节奏</div>
          <h3>推荐讲解顺序</h3>
        </div>
        <div class="section-meta">按这条线讲最容易让评委快速理解价值</div>
      </div>
      <div class="timeline-list">
        ${steps.map((step, index) => `
          <div class="timeline-item">
            <div class="timeline-date">Step ${index + 1}</div>
            <div class="timeline-dot finance"></div>
            <div class="timeline-body">${escapeHtml(step)}</div>
          </div>
        `).join("")}
      </div>
    </div>
  `;
}

function renderShowcase() {
  $("showcaseHero").innerHTML = renderShowcaseHero();
  $("showcaseScenes").innerHTML = renderShowcaseScenes();
  $("showcaseSpotlight").innerHTML = renderShowcaseSpotlight();
  $("showcaseFlow").innerHTML = renderShowcaseFlow();
  $("showcasePlaybook").innerHTML = renderShowcasePlaybook();
  $("showcaseTab").querySelectorAll("[data-showcase-scene]").forEach((button) => {
    button.addEventListener("click", async () => { await applyShowcaseScene(button.dataset.showcaseScene, { run: false }); });
  });
  $("showcaseTab").querySelectorAll("[data-showcase-run]").forEach((button) => {
    button.addEventListener("click", async () => { await applyShowcaseScene(button.dataset.showcaseRun, { run: true }); });
  });
  const fullButton = $("toggleFullscreenButton");
  if (fullButton) {
    fullButton.onclick = async () => {
      if (!document.fullscreenElement) await document.documentElement.requestFullscreen();
      else await document.exitFullscreen();
    };
  }
  const presentationButton = $("togglePresentationModeButton");
  if (presentationButton) {
    presentationButton.onclick = () => {
      document.body.classList.toggle("presentation-mode");
      presentationButton.textContent = document.body.classList.contains("presentation-mode") ? "退出大屏模式" : "切换大屏模式";
    };
  }
}

function renderTagRow(items = []) {
  if (!items.length) return "";
  return `<div class="chip-row">${items.map((item) => {
    const display = getReferenceDisplay(item);
    return `<span class="chip architecture-chip" title="${escapeAttr(display.en)}">${escapeHtml(display.zh)}</span>`;
  }).join("")}</div>`;
}

function renderArchitecturePreview(diagram) {
  const svgText = (text, x, y, extra = "") => `<text x="${x}" y="${y}" ${extra}>${escapeHtml(text)}</text>`;
  const svgTextLines = (lines, x, y, extra = "", lineHeight = 16) => `
    <text x="${x}" y="${y}" ${extra}>
      ${lines.map((line, index) => `<tspan x="${x}" dy="${index === 0 ? 0 : lineHeight}">${escapeHtml(line)}</tspan>`).join("")}
    </text>
  `;
  const previewColumns = (groups = []) => `
    <div class="architecture-preview architecture-preview-columns">
      ${groups.map((group) => `
        <div class="architecture-preview-group">
          <div class="architecture-preview-label">${escapeHtml(group.label)}</div>
          <div class="architecture-preview-stack">
            ${(group.items || []).map((item) => `<div class="architecture-preview-node">${escapeHtml(item)}</div>`).join("")}
          </div>
        </div>
      `).join("")}
    </div>
  `;
  const renderLayersSvg = () => {
    const width = 980;
    const height = 1110;
    const centerX = 490;
    const layerConfigs = [
      {
        title: "展示与交互层",
        color: "#2563eb",
        panel: { x: 56, y: 38, w: 868, h: 128, fill: "rgba(239,246,255,0.72)", stroke: "rgba(37,99,235,0.10)" },
        cards: [
          { x: 92, y: 84, w: 320, h: 54, title: "网页展示入口", lines: ["FastAPI Web App", "答辩网页与静态资源"] },
          { x: 568, y: 70, w: 300, h: 70, title: "比赛演示入口", lines: ["Streamlit Demo Pages", "多页展示与缓存演示"] },
        ],
      },
      {
        title: "应用服务层",
        color: "#0f766e",
        panel: { x: 56, y: 204, w: 868, h: 178, fill: "rgba(236,253,245,0.72)", stroke: "rgba(15,118,110,0.10)" },
        cards: [
          { x: 88, y: 254, w: 180, h: 48, title: "企业问答服务", lines: ["Chat API", "自然语言提问入口"] },
          { x: 310, y: 254, w: 180, h: 48, title: "看板聚合服务", lines: ["Dashboard APIs", "画像 / 对比 / 时间轴"] },
          { x: 532, y: 254, w: 180, h: 48, title: "自动报告服务", lines: ["Workflow APIs", "单份与批量报告"] },
          { x: 200, y: 314, w: 180, h: 48, title: "高级分析服务", lines: ["Advanced API", "股权 / 风险 / 创新"] },
          { x: 600, y: 314, w: 180, h: 48, title: "白盒溯源服务", lines: ["Whitebox API", "SQL 与证据回放"] },
        ],
      },
      {
        title: "核心分析层",
        color: "#7c3aed",
        panel: { x: 56, y: 420, w: 868, h: 208, fill: "rgba(245,243,255,0.74)", stroke: "rgba(124,58,237,0.10)" },
        cards: [
          { x: 112, y: 474, w: 300, h: 72, title: "混合检索引擎", lines: ["Retrieval Core", "路由判断 / SQL / RAG / 回答组装"] },
          { x: 556, y: 474, w: 256, h: 72, title: "高级工具引擎", lines: ["Analysis Tools", "股权 / 风险 / 创新能力计算"] },
          { x: 200, y: 566, w: 228, h: 44, title: "行业分类服务", lines: ["Industry Taxonomy"] },
          { x: 540, y: 566, w: 228, h: 44, title: "演示缓存服务", lines: ["Demo Cache"] },
        ],
      },
      {
        title: "数据构建层",
        color: "#b45309",
        panel: { x: 56, y: 666, w: 868, h: 220, fill: "rgba(255,247,237,0.78)", stroke: "rgba(180,83,9,0.10)" },
        cards: [
          { x: 86, y: 720, w: 182, h: 52, title: "底库初始化", lines: ["Database Init", "创建结构库与向量库"] },
          { x: 302, y: 720, w: 182, h: 52, title: "扩展表构建", lines: ["Expansion Builder", "创建图谱 / 风险 / 专利表"] },
          { x: 518, y: 720, w: 182, h: 52, title: "年报入库管道", lines: ["Report Pipeline", "导入年报 / 抽取财务事实"] },
          { x: 194, y: 796, w: 182, h: 52, title: "宏观数据导入", lines: ["Macro Import"] },
          { x: 592, y: 796, w: 182, h: 52, title: "图谱扩展生成", lines: ["Graph Mock Builder", "生成股权 / 风险 / 专利扩展"] },
        ],
      },
      {
        title: "存储层",
        color: "#1d4ed8",
        panel: { x: 56, y: 924, w: 868, h: 132, fill: "rgba(248,250,252,0.88)", stroke: "rgba(148,163,184,0.12)" },
        cards: [
          { x: 104, y: 978, w: 212, h: 50, title: "结构化事实库", lines: ["SQLite Database"] },
          { x: 384, y: 978, w: 212, h: 50, title: "向量检索库", lines: ["Chroma Vector Store"] },
          { x: 664, y: 966, w: 204, h: 68, title: "源文件与缓存", lines: ["Local Documents", "年报 Markdown / 宏观文件 / 演示缓存"] },
        ],
      },
    ];
    const layerLabel = (layer) => `
      <g>
        <rect x="${layer.panel.x}" y="${layer.panel.y}" width="${layer.panel.w}" height="${layer.panel.h}" rx="28" ry="28" fill="${layer.panel.fill}" stroke="${layer.panel.stroke}"></rect>
        ${svgText(layer.title, layer.panel.x + 24, layer.panel.y + 28, `font-size="17" font-weight="800" fill="${layer.color}"`)}
      </g>
    `;
    const layerCard = (card) => `
      <g>
        <rect x="${card.x}" y="${card.y}" width="${card.w}" height="${card.h}" rx="18" ry="18" fill="rgba(255,255,255,0.96)" stroke="rgba(148,163,184,0.14)"></rect>
        ${svgText(card.title, card.x + (card.w / 2), card.y + 20, 'text-anchor="middle" font-size="13.5" font-weight="800" fill="#0f172a"')}
        ${svgTextLines(card.lines, card.x + (card.w / 2), card.y + 38, 'text-anchor="middle" font-size="11.5" font-weight="700" fill="#475569"', 14)}
      </g>
    `;
    const connectors = layerConfigs.slice(0, -1).map((layer, index) => {
      const next = layerConfigs[index + 1];
      const y1 = layer.panel.y + layer.panel.h;
      const y2 = next.panel.y;
      return `
        <g>
          <line x1="${centerX}" y1="${y1 + 4}" x2="${centerX}" y2="${y2 - 18}" stroke="rgba(59,130,246,0.24)" stroke-width="4" stroke-linecap="round"></line>
          <circle cx="${centerX}" cy="${((y1 + y2) / 2) - 4}" r="16" fill="rgba(255,255,255,0.98)" stroke="rgba(45,212,191,0.18)"></circle>
          <path d="M ${centerX - 10} ${((y1 + y2) / 2) - 8} L ${centerX} ${((y1 + y2) / 2) + 4} L ${centerX + 10} ${((y1 + y2) / 2) - 8}" fill="none" stroke="#14b8a6" stroke-width="4" stroke-linecap="round" stroke-linejoin="round"></path>
        </g>
      `;
    }).join("");
    return `
      <div class="architecture-svg-shell architecture-svg-shell-layers">
        <svg class="architecture-svg" viewBox="0 0 ${width} ${height}" role="img" aria-label="模块 / 分层架构图">
          <rect x="20" y="20" width="${width - 40}" height="${height - 40}" rx="34" ry="34" fill="rgba(255,255,255,0.60)" stroke="rgba(148,163,184,0.10)"></rect>
          ${connectors}
          ${layerConfigs.map((layer) => `${layerLabel(layer)}${layer.cards.map(layerCard).join("")}`).join("")}
        </svg>
      </div>
    `;
  };
  const renderSequenceSvg = () => {
    const actors = [
      { key: "browser", label: ["浏览器", "Browser"], x: 88, w: 118, color: "#2563eb" },
      { key: "api", label: ["网页服务", "FastAPI"], x: 248, w: 130, color: "#0f766e" },
      { key: "retriever", label: ["检索分析核心", "Retrieval Core"], x: 430, w: 160, color: "#1d4ed8" },
      { key: "sqlite", label: ["结构化事实库", "SQLite"], x: 642, w: 118, color: "#b45309" },
      { key: "chroma", label: ["向量检索库", "Chroma"], x: 802, w: 118, color: "#0f766e" },
      { key: "llm", label: ["增强生成层", "DeepSeek / Local"], x: 962, w: 162, color: "#7c3aed" },
    ];
    const steps = [
      { index: "01", title: "问题提交", from: "browser", to: "api", y: 120, color: "#2563eb" },
      { index: "02", title: "转入问答核心", from: "api", to: "retriever", y: 182, color: "#0f766e" },
      { index: "03", title: "结构化查询", from: "retriever", to: "sqlite", y: 260, color: "#b45309" },
      { index: "04", title: "向量召回", from: "retriever", to: "chroma", y: 324, color: "#0f766e" },
      { index: "05", title: "答案组装", from: "retriever", to: "llm", y: 388, color: "#7c3aed" },
      { index: "06", title: "响应回传", from: "api", to: "browser", y: 464, color: "#2563eb", dashed: true },
    ];
    const actorMap = Object.fromEntries(actors.map((actor) => [actor.key, actor]));
    const width = 1210;
    const height = 536;
    const drawArrow = (step) => {
      const from = actorMap[step.from];
      const to = actorMap[step.to];
      const x1 = from.x + (from.w / 2);
      const x2 = to.x + (to.w / 2);
      const y = step.y;
      const isForward = x2 >= x1;
      const mid = (x1 + x2) / 2;
      const badgeX = mid - 116;
      const labelX = mid - 52;
      const arrowHead = isForward
        ? `<path d="M ${x2 - 12} ${y - 6} L ${x2} ${y} L ${x2 - 12} ${y + 6}" fill="none" stroke="${step.color}" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"></path>`
        : `<path d="M ${x2 + 12} ${y - 6} L ${x2} ${y} L ${x2 + 12} ${y + 6}" fill="none" stroke="${step.color}" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"></path>`;
      return `
        <g>
          <line x1="${x1}" y1="${y}" x2="${x2}" y2="${y}" stroke="${step.color}" stroke-width="3" stroke-linecap="round" ${step.dashed ? 'stroke-dasharray="9 7"' : ""}></line>
          ${arrowHead}
          <rect x="${badgeX}" y="${y - 18}" width="52" height="28" rx="14" ry="14" fill="rgba(255,255,255,0.98)" stroke="rgba(148,163,184,0.18)"></rect>
          ${svgText(step.index, badgeX + 26, y, 'text-anchor="middle" dominant-baseline="middle" font-size="12" font-weight="800" fill="#0f172a"')}
          <rect x="${labelX}" y="${y - 20}" width="190" height="32" rx="16" ry="16" fill="rgba(255,255,255,0.98)" stroke="rgba(148,163,184,0.14)"></rect>
          ${svgText(step.title, labelX + 95, y - 1, 'text-anchor="middle" dominant-baseline="middle" font-size="12" font-weight="800" fill="#0f172a"')}
        </g>
      `;
    };
    return `
      <div class="architecture-svg-shell architecture-svg-shell-sequence">
        <svg class="architecture-svg" viewBox="0 0 ${width} ${height}" role="img" aria-label="核心业务时序图">
          <rect x="20" y="20" width="${width - 40}" height="${height - 40}" rx="30" ry="30" fill="rgba(255,255,255,0.62)" stroke="rgba(148,163,184,0.12)"></rect>
          ${actors.map((actor) => {
            const cx = actor.x + (actor.w / 2);
            return `
              <g>
                <rect x="${actor.x}" y="34" width="${actor.w}" height="36" rx="18" ry="18" fill="rgba(255,255,255,0.98)" stroke="rgba(148,163,184,0.16)"></rect>
                ${svgTextLines(actor.label, cx, 47, `text-anchor="middle" font-size="12.5" font-weight="800" fill="${actor.color}"`, 13)}
                <line x1="${cx}" y1="84" x2="${cx}" y2="496" stroke="rgba(148,163,184,0.18)" stroke-width="2" stroke-dasharray="5 8"></line>
              </g>
            `;
          }).join("")}
          ${steps.map(drawArrow).join("")}
          <rect x="68" y="500" width="1060" height="16" rx="8" ry="8" fill="rgba(239,246,255,0.85)"></rect>
          ${svgText("前端最终将 answer、sources、sql、chunks 和图表规范渲染成展示卡片", 598, 508, 'text-anchor="middle" dominant-baseline="middle" font-size="11.5" font-weight="700" fill="#475569"')}
        </svg>
      </div>
    `;
  };
  const renderERSvg = () => {
    const nodes = [
      { id: "industry", label: ["行业维表", "dim_industry"], x: 62, y: 84, w: 170, h: 54, fill: "#eff6ff", stroke: "rgba(37,99,235,0.18)" },
      { id: "company", label: ["公司维表", "dim_company"], x: 62, y: 160, w: 170, h: 54, fill: "#eff6ff", stroke: "rgba(37,99,235,0.18)" },
      { id: "dictFin", label: ["财务指标字典", "dict_financial_indicator"], x: 62, y: 238, w: 170, h: 54, fill: "#eff6ff", stroke: "rgba(37,99,235,0.18)" },
      { id: "dictMacro", label: ["宏观指标字典", "dict_macro_indicator"], x: 62, y: 316, w: 170, h: 54, fill: "#eff6ff", stroke: "rgba(37,99,235,0.18)" },
      { id: "doc", label: ["文档维表", "dim_document"], x: 314, y: 122, w: 184, h: 58, fill: "#f8fafc", stroke: "rgba(148,163,184,0.22)" },
      { id: "vector", label: ["向量切片映射", "map_vector_chunk"], x: 314, y: 234, w: 184, h: 58, fill: "#ecfeff", stroke: "rgba(20,184,166,0.22)" },
      { id: "financial", label: ["财务事实表", "fact_financial_report"], x: 578, y: 102, w: 194, h: 62, fill: "#fefce8", stroke: "rgba(245,158,11,0.24)" },
      { id: "macro", label: ["宏观事实表", "fact_macro_data"], x: 578, y: 218, w: 194, h: 62, fill: "#fefce8", stroke: "rgba(245,158,11,0.24)" },
      { id: "party", label: ["主体维表", "dim_party"], x: 842, y: 72, w: 178, h: 54, fill: "#f5f3ff", stroke: "rgba(124,58,237,0.18)" },
      { id: "invest", label: ["投资关系表", "fact_investment_relation"], x: 842, y: 152, w: 178, h: 54, fill: "#f5f3ff", stroke: "rgba(124,58,237,0.18)" },
      { id: "risk", label: ["司法风险表", "fact_legal_risk"], x: 842, y: 232, w: 178, h: 54, fill: "#f5f3ff", stroke: "rgba(124,58,237,0.18)" },
      { id: "patent", label: ["专利事实表", "fact_ip_patent"], x: 842, y: 312, w: 178, h: 54, fill: "#f5f3ff", stroke: "rgba(124,58,237,0.18)" },
    ];
    const edges = [
      ["industry", "company"],
      ["company", "doc"],
      ["doc", "vector"],
      ["doc", "financial"],
      ["dictFin", "financial"],
      ["dictMacro", "macro"],
      ["company", "party"],
      ["party", "invest"],
      ["company", "invest"],
      ["company", "risk"],
      ["company", "patent"],
    ];
    const pos = Object.fromEntries(nodes.map((node) => [node.id, node]));
    const lineFor = ([from, to]) => {
      const a = pos[from];
      const b = pos[to];
      const x1 = a.x + a.w;
      const y1 = a.y + (a.h / 2);
      const x2 = b.x;
      const y2 = b.y + (b.h / 2);
      const elbow = x1 + ((x2 - x1) * 0.46);
      return `
        <path d="M ${x1} ${y1} L ${elbow} ${y1} L ${elbow} ${y2} L ${x2} ${y2}" fill="none" stroke="rgba(59,130,246,0.34)" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"></path>
        <path d="M ${x2 - 10} ${y2 - 6} L ${x2} ${y2} L ${x2 - 10} ${y2 + 6}" fill="none" stroke="rgba(59,130,246,0.34)" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"></path>
      `;
    };
    return `
      <div class="architecture-svg-shell architecture-svg-shell-er">
        <svg class="architecture-svg" viewBox="0 0 1080 420" role="img" aria-label="数据模型 ER 图">
          <rect x="18" y="20" width="1044" height="380" rx="30" ry="30" fill="rgba(255,255,255,0.60)" stroke="rgba(148,163,184,0.10)"></rect>
          <rect x="34" y="36" width="226" height="348" rx="28" ry="28" fill="rgba(239,246,255,0.55)" stroke="rgba(37,99,235,0.10)"></rect>
          <rect x="286" y="74" width="238" height="246" rx="28" ry="28" fill="rgba(248,250,252,0.86)" stroke="rgba(148,163,184,0.10)"></rect>
          <rect x="550" y="74" width="248" height="246" rx="28" ry="28" fill="rgba(254,252,232,0.78)" stroke="rgba(245,158,11,0.10)"></rect>
          <rect x="814" y="36" width="230" height="348" rx="28" ry="28" fill="rgba(245,243,255,0.78)" stroke="rgba(124,58,237,0.10)"></rect>
          ${svgText("维表层", 56, 58, 'font-size="16" font-weight="800" fill="#1d4ed8"')}
          ${svgText("文档与向量层", 308, 96, 'font-size="16" font-weight="800" fill="#475569"')}
          ${svgText("事实层", 572, 96, 'font-size="16" font-weight="800" fill="#b45309"')}
          ${svgText("扩展分析层", 836, 58, 'font-size="16" font-weight="800" fill="#7c3aed"')}
          ${edges.map(lineFor).join("")}
          ${nodes.map((node) => `
            <g>
              <rect x="${node.x}" y="${node.y}" width="${node.w}" height="${node.h}" rx="18" ry="18" fill="${node.fill}" stroke="${node.stroke}"></rect>
              ${svgTextLines(node.label, node.x + (node.w / 2), node.y + 28, 'text-anchor="middle" font-size="14" font-weight="800" fill="#0f172a"', 16)}
            </g>
          `).join("")}
        </svg>
      </div>
    `;
  };
  const renderDeploymentSvg = () => `
    <div class="architecture-svg-shell architecture-svg-shell-deployment">
      <svg class="architecture-svg" viewBox="0 0 980 500" role="img" aria-label="部署架构图">
        <rect x="220" y="24" width="730" height="452" rx="32" ry="32" fill="rgba(255,255,255,0.60)" stroke="rgba(148,163,184,0.10)"></rect>
        ${svgText("本机运行节点", 252, 56, 'font-size="18" font-weight="800" fill="#0f172a"')}

        <rect x="36" y="118" width="154" height="60" rx="22" ry="22" fill="rgba(239,246,255,0.96)" stroke="rgba(37,99,235,0.14)"></rect>
        ${svgTextLines(["浏览器", "Browser"], 113, 140, 'text-anchor="middle" font-size="14" font-weight="800" fill="#2563eb"', 16)}
        <rect x="36" y="232" width="154" height="60" rx="22" ry="22" fill="rgba(239,246,255,0.96)" stroke="rgba(37,99,235,0.14)"></rect>
        ${svgTextLines(["比赛演示端", "Streamlit"], 113, 254, 'text-anchor="middle" font-size="14" font-weight="800" fill="#2563eb"', 16)}

        <rect x="278" y="96" width="214" height="74" rx="24" ry="24" fill="rgba(236,253,245,0.98)" stroke="rgba(15,118,110,0.14)"></rect>
        ${svgText("网页服务入口", 300, 126, 'font-size="18" font-weight="800" fill="#0f766e"')}
        ${svgText("FastAPI Web Service", 300, 150, 'font-size="12" font-weight="700" fill="#475569"')}

        <rect x="278" y="214" width="214" height="74" rx="24" ry="24" fill="rgba(236,253,245,0.98)" stroke="rgba(15,118,110,0.14)"></rect>
        ${svgText("比赛演示进程", 300, 244, 'font-size="18" font-weight="800" fill="#0f766e"')}
        ${svgText("Streamlit Demo Process", 300, 268, 'font-size="12" font-weight="700" fill="#475569"')}

        <rect x="562" y="118" width="312" height="124" rx="28" ry="28" fill="rgba(245,243,255,0.98)" stroke="rgba(124,58,237,0.14)"></rect>
        ${svgText("共享代码底座", 588, 148, 'font-size="18" font-weight="800" fill="#7c3aed"')}
        <rect x="588" y="164" width="260" height="18" rx="9" ry="9" fill="rgba(239,246,255,0.92)"></rect>
        <rect x="588" y="192" width="260" height="18" rx="9" ry="9" fill="rgba(239,246,255,0.92)"></rect>
        <rect x="588" y="220" width="260" height="18" rx="9" ry="9" fill="rgba(239,246,255,0.92)"></rect>
        ${svgText("网页静态资源 / Web UI", 604, 177, 'font-size="12" font-weight="700" fill="#7c3aed"')}
        ${svgText("检索分析核心 / Core", 604, 205, 'font-size="12" font-weight="700" fill="#7c3aed"')}
        ${svgText("数据构建脚本 / DataOps", 604, 233, 'font-size="12" font-weight="700" fill="#7c3aed"')}

        <rect x="320" y="344" width="520" height="96" rx="28" ry="28" fill="rgba(255,247,237,0.98)" stroke="rgba(180,83,9,0.14)"></rect>
        ${svgText("本地数据层", 346, 374, 'font-size="18" font-weight="800" fill="#b45309"')}
        <rect x="346" y="390" width="468" height="16" rx="8" ry="8" fill="rgba(255,255,255,0.82)"></rect>
        <rect x="346" y="414" width="468" height="16" rx="8" ry="8" fill="rgba(255,255,255,0.82)"></rect>
        ${svgText("结构化库 / 向量库 / 年报源文件", 362, 402, 'font-size="12" font-weight="700" fill="#b45309"')}
        ${svgText("演示缓存 / 宏观原始数据", 362, 426, 'font-size="12" font-weight="700" fill="#b45309"')}

        <path d="M 190 148 C 226 148, 244 132, 278 132" fill="none" stroke="#2563eb" stroke-width="4" stroke-linecap="round"></path>
        <path d="M 190 262 C 226 262, 244 250, 278 250" fill="none" stroke="#2563eb" stroke-width="4" stroke-linecap="round"></path>
        <path d="M 492 132 C 520 132, 536 158, 562 178" fill="none" stroke="#0f766e" stroke-width="4" stroke-linecap="round"></path>
        <path d="M 492 250 C 520 250, 536 224, 562 196" fill="none" stroke="#0f766e" stroke-width="4" stroke-linecap="round"></path>
        <path d="M 652 242 C 652 278, 628 314, 580 344" fill="none" stroke="#7c3aed" stroke-width="4" stroke-linecap="round"></path>
      </svg>
    </div>
  `;
  switch (diagram.key) {
    case "context":
      return previewColumns([
        { label: "用户与入口", items: ["评委/分析师", "浏览器", "Streamlit 页面入口"] },
        { label: "网页与核心", items: ["FastAPI 网页服务", "检索分析核心", "高级分析工具"] },
        { label: "存储与数据", items: ["SQLite", "Chroma", "Final_md", "raw_macro"] },
        { label: "可选增强", items: ["DeepSeek API"] },
      ]);
    case "layers":
      return renderLayersSvg();
    case "sequence":
      return renderSequenceSvg();
    case "er":
      return renderERSvg();
    case "deployment":
      return renderDeploymentSvg();
    default:
      return "";
  }
}

function renderArchitectureDiagramCard(diagram, index = 0) {
  const previewOnly = diagram.displayMode === "preview";
  return `
    <div class="panel dashboard-panel architecture-card" data-project-reveal="diagram">
      <div class="section-header">
        <div class="architecture-card-headline">
          <div class="architecture-card-index">${String(index + 1).padStart(2, "0")}</div>
          <div>
            <div class="eyebrow">必要图表</div>
            <h3>${escapeHtml(diagram.title)}</h3>
          </div>
        </div>
        <div class="section-meta">${escapeHtml(diagram.summary)}</div>
      </div>
      <div class="architecture-diagram-shell${previewOnly ? " architecture-diagram-shell-preview" : ""}">
        ${previewOnly ? `
          <div class="architecture-visual-primary">${renderArchitecturePreview(diagram)}</div>
          <details class="architecture-code-toggle">
            <summary>查看 Mermaid 定义</summary>
            <pre class="mermaid-fallback">${escapeHtml(diagram.mermaid)}</pre>
          </details>
        ` : `
          <div class="mermaid architecture-mermaid" data-mermaid-key="${escapeAttr(diagram.key)}">
${diagram.mermaid}
          </div>
          <div class="architecture-visual-fallback" hidden>${renderArchitecturePreview(diagram)}</div>
          <pre class="mermaid-fallback" hidden>${escapeHtml(diagram.mermaid)}</pre>
        `}
      </div>
      <div class="architecture-meta-grid">
        <div class="advanced-panel">
          <strong>这张图说明了什么</strong>
          <div class="advanced-panel-body">${escapeHtml(diagram.summary)}</div>
        </div>
        <div class="advanced-panel">
          <strong>涉及哪些关键目录、模块、服务、表、接口</strong>
          ${renderTagRow(diagram.references || [])}
        </div>
      </div>
      <div class="architecture-meta-grid">
        <div class="advanced-panel">
          <strong>当前设计的优点</strong>
          <ul class="architecture-list">${(diagram.strengths || []).map((item) => `<li>${escapeHtml(item)}</li>`).join("")}</ul>
        </div>
        <div class="advanced-panel">
          <strong>潜在风险、耦合点、技术债</strong>
          <ul class="architecture-list">${(diagram.risks || []).map((item) => `<li>${escapeHtml(item)}</li>`).join("")}</ul>
        </div>
      </div>
    </div>
  `;
}

function renderProjectOverview() {
  const stats = state.stats || {};
  const modeLabel = state.deepseekEnabled ? "当前环境已启用可选 DeepSeek 增强" : "当前环境处于本地检索模式，DeepSeek 为可选增强";
  $("projectOverview").innerHTML = `
    <div class="panel dashboard-panel project-hero" data-project-reveal="hero">
      <div class="section-header">
        <div>
          <div class="eyebrow">项目介绍</div>
          <h3>医药生物企业智能分析与决策支持系统</h3>
        </div>
        <div class="section-meta">${escapeHtml(modeLabel)}</div>
      </div>
      <div class="summary-card" style="margin-top:0;">
        <div class="label">项目定位</div>
        <div class="value">这是一个面向医药生物行业的本地化企业分析系统，围绕年报问答、公司画像、同业比较、宏观联动、图谱分析、白盒溯源和自动化报告构建完整展示链路。当前真实技术底座是 FastAPI / Streamlit 双入口、SQLite 结构化库、Chroma 向量库、Markdown 年报目录与可选 DeepSeek 增强。</div>
      </div>
      <div class="dashboard-cards compact" style="margin-top:16px;">
        <div class="dashboard-card blue"><div class="label">企业数</div><div class="value">${escapeHtml(String(stats.companies ?? "-"))}</div></div>
        <div class="dashboard-card teal"><div class="label">文档数</div><div class="value">${escapeHtml(String(stats.documents ?? "-"))}</div></div>
        <div class="dashboard-card amber"><div class="label">财务事实数</div><div class="value">${escapeHtml(String(stats.financial_facts ?? "-"))}</div></div>
        <div class="dashboard-card cyan"><div class="label">宏观事实数</div><div class="value">${escapeHtml(String(stats.macro_facts ?? "-"))}</div></div>
      </div>
      <div class="project-facts-grid">
        ${PROJECT_FACTS.map((item) => `
          <div class="project-fact-card" data-project-reveal="fact">
            <div class="label">${escapeHtml(item.label)}</div>
            <div class="value">${escapeHtml(item.value)}</div>
            <div class="card-meta">${escapeHtml(item.detail)}</div>
          </div>
        `).join("")}
      </div>
    </div>

    <div class="project-grid">
      <div class="panel dashboard-panel" data-project-reveal="section">
        <div class="section-header">
          <div>
            <div class="eyebrow">真实模块</div>
            <h3>代码仓库中的核心组成</h3>
          </div>
          <div class="section-meta">按目录而不是按概念梳理</div>
        </div>
        <div class="project-module-grid">
          ${PROJECT_MODULES.map((item) => `
            <div class="project-module-card" data-project-reveal="module">
              <strong>${escapeHtml(item.title)}</strong>
              <div class="card-meta">${escapeHtml(item.path)}</div>
              <p>${escapeHtml(item.body)}</p>
            </div>
          `).join("")}
        </div>
      </div>

      <div class="panel dashboard-panel" data-project-reveal="section">
        <div class="section-header">
          <div>
            <div class="eyebrow">运行链路</div>
            <h3>从页面请求到数据结果</h3>
          </div>
          <div class="section-meta">对应 FastAPI 与 core 主链路</div>
        </div>
        <div class="timeline-list">
          ${PROJECT_RUNTIME_STEPS.map((item, index) => `
            <div class="timeline-item">
              <div class="timeline-date">Step ${index + 1}</div>
              <div class="timeline-dot finance"></div>
              <div class="timeline-body">${escapeHtml(item)}</div>
            </div>
          `).join("")}
        </div>
      </div>
    </div>

    <div class="panel dashboard-panel" data-project-reveal="overview">
      <div class="section-header">
        <div>
          <div class="eyebrow">项目架构总览</div>
          <h3>核心技术、模块与调用关系</h3>
        </div>
        <div class="section-meta">适合在汇报第一页直接使用</div>
      </div>
      <div class="summary-card" style="margin-top:0;">
        <div class="value">该项目是一个面向医药生物行业的企业运营分析与决策支持系统，目标是把年报 Markdown、结构化财务事实、宏观指标、股权/风险/专利扩展信息整合到同一套可展示、可追溯的分析链路中。系统同时保留了 Streamlit 比赛版入口和 FastAPI 自建网页入口，底层统一依赖 SQLite 作为结构化事实库、Chroma 作为向量检索库，并通过 DeepSeek 作为可选增强能力。核心模块包括数据构建层、检索分析层、展示交互层、演示缓存层和测试层。总体调用关系是：dataops 先构建数据库与向量库，core 层在运行时完成 SQL、RAG 和高级工具分析，apps 与 webapp 再将这些能力封装成页面和接口对外提供服务。当前架构风格更接近单仓单体应用，带有前后端分离网页与 Streamlit 多入口并存的混合展示形态。</div>
      </div>
    </div>

    <div class="architecture-diagram-grid">
      ${PROJECT_DIAGRAMS.map((item, index) => renderArchitectureDiagramCard(item, index)).join("")}
    </div>

    <div class="project-grid">
      <div class="panel dashboard-panel" data-project-reveal="panel">
        <div class="section-header">
          <div>
            <div class="eyebrow">架构问题清单</div>
            <h3>当前主要问题</h3>
          </div>
          <div class="section-meta">来自代码现状，而不是理想状态</div>
        </div>
        <ul class="architecture-list architecture-list-spacious">${PROJECT_ISSUES.map((item) => `<li>${escapeHtml(item)}</li>`).join("")}</ul>
      </div>

      <div class="panel dashboard-panel" data-project-reveal="panel">
        <div class="section-header">
          <div>
            <div class="eyebrow">优化建议清单</div>
            <h3>下一步演进方向</h3>
          </div>
          <div class="section-meta">偏工程化落地</div>
        </div>
        <ul class="architecture-list architecture-list-spacious">${PROJECT_RECOMMENDATIONS.map((item) => `<li>${escapeHtml(item)}</li>`).join("")}</ul>
      </div>
    </div>

    <div class="project-grid">
      <div class="panel dashboard-panel" data-project-reveal="panel">
        <div class="section-header">
          <div>
            <div class="eyebrow">假设与待确认项</div>
            <h3>当前无法直接从代码确认的点</h3>
          </div>
          <div class="section-meta">明确写出“无法确认”更稳妥</div>
        </div>
        <ul class="architecture-list architecture-list-spacious">${PROJECT_ASSUMPTIONS.map((item) => `<li>${escapeHtml(item)}</li>`).join("")}</ul>
      </div>
      <div class="panel dashboard-panel" data-project-reveal="panel">
        <div class="section-header">
          <div>
            <div class="eyebrow">补充说明</div>
            <h3>汇报时建议主动说明</h3>
          </div>
          <div class="section-meta">这些点更贴近代码真实状态</div>
        </div>
        <div class="quick-list">
          ${PROJECT_HIGHLIGHTS.map((item) => `<div class="project-note" data-project-reveal="note">${escapeHtml(item)}</div>`).join("")}
        </div>
      </div>
    </div>
  `;
}

function buildEvidenceId(label = "", fallback = "") {
  return `evidence-${slugify(label || fallback)}`;
}

function renderEvidencePanel(result = {}) {
  const chunks = result.chunks || result.rag_chunks || [];
  if (!chunks.length) return "";
  return `
    <div class="detail-block">
      <div class="detail-title">
        <strong>证据定位</strong>
        <span class="detail-tag">可跳转原文片段</span>
      </div>
      <div class="evidence-list">
        ${chunks.map((chunk, index) => {
          const meta = chunk.metadata || {};
          const label = `${meta.source || "未知来源"} 第${meta.page ?? "?"}页`;
          return `
            <div id="${buildEvidenceId(label, `chunk-${index + 1}`)}" class="evidence-card">
              <div class="evidence-head">
                <strong>${escapeHtml(label)}</strong>
                <span class="card-meta">${escapeHtml(meta.file_path || "")}</span>
              </div>
              <div class="source-snippet">${escapeHtml(chunk.text || "")}</div>
            </div>
          `;
        }).join("")}
      </div>
    </div>
  `;
}

function renderDashboard(payload = {}) {
  $("dashboardOverview").innerHTML = renderImportOverview(payload.import_overview || {});
  $("trendDashboard").innerHTML = renderTrendOverview(payload.trend_overview || {});
  $("rankingDashboard").innerHTML = renderRankingOverview(payload.ranking_overview || {});
  $("alertDashboard").innerHTML = renderAlertOverview(payload.alert_overview || {});
  $("macroDashboard").innerHTML = renderMacroOverview(payload.macro_overview || {});
  schedulePanelRefresh($("dashboardTab"));
}

function renderVizBlocks(vizBlocks = []) {
  if (!vizBlocks.length) return "";
  const items = vizBlocks.map((block) => {
    const chartHost = block.option ? `<div class="viz-chart-host" data-echart='${escapeAttr(JSON.stringify({ kind: "viz_block", payload: block }))}'></div>` : "";
    return `
      <div class="viz-card">
        <h4>${escapeHtml(block.title || "分析图表")}</h4>
        ${chartHost}
        ${renderVizFallback(block)}
      </div>
    `;
  }).join("");
  return `<div class="viz-grid">${items}</div>`;
}

function renderGraphSvg(block = {}) {
  const series = (block.option?.series || []).find((item) => item?.type === "graph") || {};
  const nodes = (series.data || []).slice(0, 12);
  const links = series.links || [];
  if (!nodes.length) return "";
  const width = 720;
  const height = 360;
  const centerX = width / 2;
  const centerY = height / 2;
  const rootNode = nodes.find((node) => Number(node.level) === 0) || nodes[0];
  const ringNodes = nodes.filter((node) => node !== rootNode);
  const levels = [...new Set(ringNodes.map((node) => Math.max(1, Number(node.level) || 1)))].sort((a, b) => a - b);
  const grouped = new Map(levels.map((level) => [level, ringNodes.filter((node) => Math.max(1, Number(node.level) || 1) === level)]));
  const positions = new Map();
  positions.set(rootNode.id || rootNode.name, { x: centerX, y: centerY, r: 26, fill: "#2563eb" });
  levels.forEach((level) => {
    const items = grouped.get(level) || [];
    const radius = 86 + ((level - 1) * 60);
    items.forEach((node, index) => {
      const angle = (-Math.PI / 2) + ((Math.PI * 2 * index) / Math.max(items.length, 1));
      positions.set(node.id || node.name, {
        x: centerX + (Math.cos(angle) * radius),
        y: centerY + (Math.sin(angle) * radius),
        r: level === 1 ? 18 : 14,
        fill: level === 1 ? "#38bdf8" : "#14b8a6",
      });
    });
  });
  const edgeLines = links.map((link) => {
    const source = positions.get(link.source);
    const target = positions.get(link.target);
    if (!source || !target) return "";
    return `<line x1="${source.x}" y1="${source.y}" x2="${target.x}" y2="${target.y}" stroke="rgba(37,99,235,0.25)" stroke-width="2" />`;
  }).join("");
  const circles = nodes.map((node) => {
    const position = positions.get(node.id || node.name);
    if (!position) return "";
    const label = String(node.name || node.id || "节点");
    const shortLabel = label.length > 10 ? `${label.slice(0, 10)}…` : label;
    return `
      <g>
        <circle cx="${position.x}" cy="${position.y}" r="${position.r}" fill="${position.fill}" fill-opacity="${node === rootNode ? "1" : "0.88"}" />
        <text x="${position.x}" y="${position.y + position.r + 18}" text-anchor="middle" font-size="12" fill="#334155">${escapeHtml(shortLabel)}</text>
      </g>
    `;
  }).join("");
  return `
    <div class="viz-svg-shell">
      <svg class="viz-svg" viewBox="0 0 ${width} ${height}" role="img" aria-label="${escapeAttr(block.title || "股权关系图谱")}">
        ${edgeLines}
        ${circles}
      </svg>
    </div>
  `;
}

function renderRadarSvg(block = {}) {
  const indicators = block.option?.radar?.indicator || [];
  const values = (((block.option?.series || [])[0] || {}).data || [])[0]?.value || [];
  if (!indicators.length) return "";
  const width = 420;
  const height = 340;
  const centerX = width / 2;
  const centerY = height / 2;
  const radius = 112;
  const levels = [0.25, 0.5, 0.75, 1];
  const pointsForScale = (scale) => indicators.map((indicator, index) => {
    const angle = (-Math.PI / 2) + ((Math.PI * 2 * index) / indicators.length);
    const length = radius * scale;
    return `${(centerX + (Math.cos(angle) * length)).toFixed(1)},${(centerY + (Math.sin(angle) * length)).toFixed(1)}`;
  }).join(" ");
  const dataPoints = indicators.map((indicator, index) => {
    const angle = (-Math.PI / 2) + ((Math.PI * 2 * index) / indicators.length);
    const maxValue = Number(indicator?.max) || 100;
    const ratio = Math.max(0, Math.min(1, (Number(values[index]) || 0) / maxValue));
    return {
      x: centerX + (Math.cos(angle) * radius * ratio),
      y: centerY + (Math.sin(angle) * radius * ratio),
      labelX: centerX + (Math.cos(angle) * (radius + 28)),
      labelY: centerY + (Math.sin(angle) * (radius + 28)),
      name: indicator?.name || `维度${index + 1}`,
      value: Number(values[index]) || 0,
    };
  });
  return `
    <div class="viz-svg-shell">
      <svg class="viz-svg radar-svg" viewBox="0 0 ${width} ${height}" role="img" aria-label="${escapeAttr(block.title || "风险创新雷达图")}">
        ${levels.map((scale) => `<polygon points="${pointsForScale(scale)}" fill="none" stroke="rgba(148,163,184,0.24)" stroke-width="1"></polygon>`).join("")}
        ${indicators.map((indicator, index) => {
          const angle = (-Math.PI / 2) + ((Math.PI * 2 * index) / indicators.length);
          const endX = centerX + (Math.cos(angle) * radius);
          const endY = centerY + (Math.sin(angle) * radius);
          return `<line x1="${centerX}" y1="${centerY}" x2="${endX.toFixed(1)}" y2="${endY.toFixed(1)}" stroke="rgba(148,163,184,0.28)" stroke-width="1"></line>`;
        }).join("")}
        <polygon points="${dataPoints.map((point) => `${point.x.toFixed(1)},${point.y.toFixed(1)}`).join(" ")}" fill="rgba(37,99,235,0.18)" stroke="#2563eb" stroke-width="2"></polygon>
        ${dataPoints.map((point) => `
          <g>
            <circle cx="${point.x.toFixed(1)}" cy="${point.y.toFixed(1)}" r="4" fill="#2563eb"></circle>
            <text x="${point.labelX.toFixed(1)}" y="${point.labelY.toFixed(1)}" text-anchor="middle" font-size="12" fill="#334155">${escapeHtml(point.name)}</text>
          </g>
        `).join("")}
      </svg>
    </div>
  `;
}

function renderVizFallback(block = {}) {
  if (block.type === "graph") {
    const series = (block.option?.series || []).find((item) => item?.type === "graph") || {};
    const nodes = series.data || [];
    const links = series.links || [];
    const previews = nodes.slice(0, 6).map((node) => node.name || node.id).filter(Boolean);
    return `
      ${renderGraphSvg(block)}
      <div class="viz-fallback-grid">
        <div class="viz-fallback-item"><strong>节点数</strong><div>${escapeHtml(String(nodes.length))}</div></div>
        <div class="viz-fallback-item"><strong>关系数</strong><div>${escapeHtml(String(links.length))}</div></div>
        <div class="viz-fallback-item"><strong>关键节点</strong><div>${escapeHtml(previews.join("、") || "暂无")}</div></div>
      </div>
    `;
  }
  if (block.type === "radar") {
    const indicators = block.option?.radar?.indicator || [];
    const values = (((block.option?.series || [])[0] || {}).data || [])[0]?.value || [];
    const rows = indicators.map((indicator, index) => ({
      name: indicator?.name || `维度${index + 1}`,
      value: Number(values[index]) || 0,
    }));
    return `
      ${renderRadarSvg(block)}
      <div class="viz-bar-list">
        ${rows.map((row) => `
          <div class="viz-bar-row">
            <strong>${escapeHtml(row.name)}</strong>
            <div class="viz-bar-track"><div class="viz-bar-fill" style="width:${Math.max(0, Math.min(100, row.value)).toFixed(0)}%;"></div></div>
            <span>${escapeHtml(String(row.value))}</span>
          </div>
        `).join("")}
      </div>
    `;
  }
  return "";
}

function renderAdvancedVizBlocks(vizBlocks = []) {
  if (!vizBlocks.length) return "";
  return `
    <div class="viz-grid advanced-viz-grid">
      ${vizBlocks.map((block) => `
        <div class="viz-card advanced-viz-card">
          <div class="detail-title">
            <strong>${escapeHtml(block.title || "高级分析图表")}</strong>
            <span class="detail-tag">${escapeHtml(block.type === "graph" ? "图谱视图" : "雷达视图")}</span>
          </div>
          ${renderVizFallback(block)}
        </div>
      `).join("")}
    </div>
  `;
}

function buildChartOption(chartSpec) {
  const rows = (chartSpec.rows || []).slice(0, 12);
  const xKey = chartSpec.x;
  const yKey = chartSpec.y;
  const seriesKey = chartSpec.series;
  const uniqueX = [...new Set(rows.map((row) => String(row[xKey] ?? "-")))];
  if (seriesKey) {
    const uniqueSeries = [...new Set(rows.map((row) => String(row[seriesKey] ?? "系列")))];
    return {
      color: ["#2563eb", "#0ea5e9", "#14b8a6", "#f59e0b", "#ef4444"],
      tooltip: { trigger: "axis", confine: true },
      legend: { top: 0 },
      grid: { left: 44, right: 18, top: 40, bottom: 36, containLabel: true },
      xAxis: { type: "category", data: uniqueX, axisLabel: { color: "#475569" }, axisLine: { lineStyle: { color: "#cbd5e1" } } },
      yAxis: { type: "value", axisLabel: { color: "#475569" }, splitLine: { lineStyle: { color: "#e2e8f0" } } },
      series: uniqueSeries.map((seriesName) => ({
        name: seriesName,
        type: chartSpec.chart_type === "line" ? "line" : "bar",
        smooth: chartSpec.chart_type === "line",
        data: uniqueX.map((xValue) => {
          const row = rows.find((item) => String(item[xKey] ?? "-") === xValue && String(item[seriesKey] ?? "系列") === seriesName);
          return Number(row?.[yKey]) || 0;
        }),
      })),
    };
  }
  return {
    color: ["#2563eb"],
    tooltip: { trigger: "axis", confine: true },
    grid: { left: 44, right: 18, top: 20, bottom: 36, containLabel: true },
    xAxis: { type: "category", data: uniqueX, axisLabel: { color: "#475569", interval: 0, rotate: uniqueX.some((value) => value.length > 8) ? 20 : 0 }, axisLine: { lineStyle: { color: "#cbd5e1" } } },
    yAxis: { type: "value", axisLabel: { color: "#475569" }, splitLine: { lineStyle: { color: "#e2e8f0" } } },
    series: [{
      type: chartSpec.chart_type === "line" ? "line" : "bar",
      smooth: chartSpec.chart_type === "line",
      barMaxWidth: 42,
      data: rows.map((row) => Number(row[yKey]) || 0),
    }],
  };
}

function isRenderableChartNode(node) {
  if (!node || !node.isConnected) return false;
  const rect = node.getBoundingClientRect();
  return rect.width > 0 && rect.height > 0;
}

function initializeCharts(root = document) {
  if (!window.echarts || !root?.querySelectorAll) return;
  root.querySelectorAll("[data-echart]").forEach((node) => {
    if (!isRenderableChartNode(node)) return;
    const raw = node.getAttribute("data-echart");
    if (!raw) return;
    let parsed;
    try {
      parsed = JSON.parse(raw);
    } catch {
      return;
    }
    const existingChart = window.echarts.getInstanceByDom(node);
    const chart = existingChart || window.echarts.init(node, null, { renderer: "canvas" });
    const option = parsed.kind === "chart_spec" ? buildChartOption(parsed.payload || {}) : (parsed.payload?.option || {});
    chart.setOption(option, true);
    if (parsed.kind === "viz_block" && parsed.payload?.type === "graph" && node.dataset.graphBound !== "true") {
      chart.on("click", (params) => {
        const name = params?.data?.name || params?.name;
        const series = (((parsed.payload || {}).option || {}).series || [])[0] || {};
        const links = series.links || [];
        const related = links.filter((item) => item.source === name || item.target === name).slice(0, 8);
        $("advancedNodeDetail").innerHTML = `
          <div class="node-detail-card">
            <div class="node-detail-title">节点详情</div>
            <div class="summary-card" style="margin-top:0;">
              <div class="label">当前节点</div>
              <div class="value">${escapeHtml(String(name || "未知节点"))}</div>
            </div>
            <div class="kv-grid" style="margin-top:12px;">
              ${related.length ? related.map((item) => `<div class="kv-item"><strong>${escapeHtml(String(item.source))}</strong> → ${escapeHtml(String(item.target))}<div style="margin-top:6px;color:#64748b;">关联值：${escapeHtml(String(item.value ?? "-"))}</div></div>`).join("") : '<div class="kv-item">当前节点暂无更多关系信息。</div>'}
            </div>
          </div>
        `;
        scrollToBottom();
      });
      node.dataset.graphBound = "true";
    }
    node.dataset.chartReady = "true";
    chart.resize();
  });
}

function resizeCharts(root = document) {
  if (!window.echarts || !root?.querySelectorAll) return;
  root.querySelectorAll("[data-echart]").forEach((node) => {
    if (!isRenderableChartNode(node)) return;
    const chart = window.echarts.getInstanceByDom(node);
    if (chart) chart.resize();
  });
}

function schedulePanelRefresh(root = document) {
  if (!root) return;
  const refresh = () => {
    initializeCharts(root);
    initializeMermaid(root);
    initializeInteractiveControls(root);
    resizeCharts(root);
  };
  refresh();
  window.requestAnimationFrame(refresh);
  window.setTimeout(refresh, 120);
}

function initializeMermaid(root = document) {
  if (!root?.querySelectorAll) return;
  const toggleArchitectureFallback = (node, showVisual = false, showCode = false) => {
    const shell = node.parentElement;
    const visual = shell?.querySelector(".architecture-visual-fallback");
    const code = shell?.querySelector(".mermaid-fallback");
    if (visual) visual.hidden = !showVisual;
    if (code) code.hidden = !showCode;
  };
  if (!window.mermaid) {
    root.querySelectorAll(".architecture-mermaid").forEach((node) => {
      toggleArchitectureFallback(node, true, false);
    });
    return;
  }
  if (!mermaidBootstrapped) {
    window.mermaid.initialize({
      startOnLoad: false,
      securityLevel: "loose",
      theme: "base",
      themeVariables: {
        primaryColor: "#eff6ff",
        primaryBorderColor: "#93c5fd",
        primaryTextColor: "#0f172a",
        lineColor: "#64748b",
        secondaryColor: "#ecfeff",
        tertiaryColor: "#f8fafc",
        fontFamily: "SF Pro Text, PingFang SC, Helvetica Neue, sans-serif",
      },
      flowchart: { curve: "basis" },
    });
    mermaidBootstrapped = true;
  }
  root.querySelectorAll(".architecture-mermaid").forEach((node) => {
    if (node.dataset.mermaidRendered === "true" || node.dataset.mermaidRendered === "pending") return;
    node.dataset.mermaidRendered = "pending";
    Promise.resolve(window.mermaid.run({ nodes: [node] }))
      .then(() => {
        node.dataset.mermaidRendered = "true";
        toggleArchitectureFallback(node, false, false);
        window.requestAnimationFrame(() => {
          const svg = node.querySelector("svg");
          const rect = svg?.getBoundingClientRect();
          if (!svg || !rect || rect.width < 80 || rect.height < 80) {
            toggleArchitectureFallback(node, true, false);
          }
        });
      })
      .catch(() => {
        node.dataset.mermaidRendered = "error";
        toggleArchitectureFallback(node, true, false);
      });
  });
}

function clearProjectRevealTimers() {
  state.projectRevealTimers.forEach((timer) => window.clearTimeout(timer));
  state.projectRevealTimers = [];
}

function playProjectReveal(root = $("projectTab")) {
  if (!root?.querySelectorAll) return;
  clearProjectRevealTimers();
  const revealOrder = {
    hero: 0,
    fact: 1,
    section: 2,
    module: 3,
    overview: 4,
    diagram: 5,
    panel: 6,
    note: 7,
    default: 8,
  };
  const revealCounts = new Map();
  const items = [...root.querySelectorAll("[data-project-reveal]")];
  items.forEach((item) => {
    const type = item.dataset.projectReveal || "default";
    const count = revealCounts.get(type) || 0;
    revealCounts.set(type, count + 1);
    const groupIndex = revealOrder[type] ?? revealOrder.default;
    const delay = 140 + (groupIndex * 160) + (count * 90);
    item.style.setProperty("--project-reveal-delay", `${delay}ms`);
    item.style.setProperty("--project-reveal-offset", `${type === "diagram" ? 34 : type === "hero" ? 18 : 24}px`);
    item.classList.remove("project-revealed");
    item.classList.add("project-reveal-item");
  });
  items.forEach((item, index) => {
    const delay = Number.parseInt(item.style.getPropertyValue("--project-reveal-delay"), 10) || (80 + (index * 85));
    const timer = window.setTimeout(() => {
      item.classList.add("project-revealed");
    }, delay);
    state.projectRevealTimers.push(timer);
  });
}

function initializeInteractiveControls(root = document) {
  root.querySelectorAll("[data-evidence-target]").forEach((button) => {
    if (button.dataset.bound === "true") return;
    button.dataset.bound = "true";
    button.addEventListener("click", (event) => {
      event.preventDefault();
      event.stopPropagation();
      const target = document.getElementById(button.dataset.evidenceTarget || "");
      if (!target) return;
      target.scrollIntoView({ behavior: "smooth", block: "center" });
      target.classList.add("focus-ring");
      window.setTimeout(() => target.classList.remove("focus-ring"), 1400);
    });
  });
}

function persistChatHistory() {
  try {
    localStorage.setItem(CHAT_HISTORY_KEY, JSON.stringify(state.history.slice(-30)));
  } catch {}
}

function restoreChatHistory() {
  try {
    const raw = localStorage.getItem(CHAT_HISTORY_KEY);
    state.history = raw ? JSON.parse(raw) : [];
  } catch {
    state.history = [];
  }
  if (!state.history.length) {
    $("chatMessages").innerHTML = '<div class="empty-history">历史对话会保存在当前浏览器中，刷新页面后仍可继续。</div>';
    return false;
  }
  $("chatMessages").innerHTML = "";
  state.history.forEach((item) => {
    const wrapper = document.createElement("div");
    wrapper.className = `message ${item.role}`;
    wrapper.innerHTML = `<div class="message-card">${item.html}</div>`;
    $("chatMessages").appendChild(wrapper);
  });
  schedulePanelRefresh($("chatMessages"));
  return true;
}

function clearChatHistory() {
  state.history = [];
  state.lastChatResult = null;
  persistChatHistory();
  $("chatMessages").innerHTML = '<div class="empty-history">聊天记录已清空，你可以重新开始新的分析会话。</div>';
  renderFollowups([]);
}

function persistSnapshots() {
  try {
    localStorage.setItem(SNAPSHOT_KEY, JSON.stringify(state.snapshots.slice(0, 20)));
  } catch {}
}

function restoreSnapshots() {
  try {
    const raw = localStorage.getItem(SNAPSHOT_KEY);
    state.snapshots = raw ? JSON.parse(raw) : [];
  } catch {
    state.snapshots = [];
  }
}

function saveSnapshot(type, title, payload) {
  const snapshot = {
    id: `snapshot-${Date.now()}`,
    type,
    title: title || "未命名快照",
    createdAt: formatNowLabel(),
    payload,
  };
  state.snapshots.unshift(snapshot);
  state.snapshots = state.snapshots.slice(0, 20);
  persistSnapshots();
  renderSnapshots();
}

function renderSnapshotPreview(snapshot) {
  if (!snapshot) {
    $("snapshotPreview").innerHTML = "";
    return;
  }
  if (snapshot.type === "dashboard") {
    $("snapshotPreview").innerHTML = `<div class="report-card" style="padding:18px 20px;">${renderImportOverview(snapshot.payload.import_overview || {})}${renderTrendOverview(snapshot.payload.trend_overview || {})}${renderRankingOverview(snapshot.payload.ranking_overview || {})}${renderAlertOverview(snapshot.payload.alert_overview || {})}${renderMacroOverview(snapshot.payload.macro_overview || {})}</div>`;
  } else if (snapshot.type === "chat") {
    $("snapshotPreview").innerHTML = `<div class="report-card" style="padding:18px 20px;">${buildAssistantHtml(snapshot.payload.result || {}, snapshot.payload.question || "")}</div>`;
  } else if (snapshot.type === "workflow") {
    $("snapshotPreview").innerHTML = `<div class="report-card" style="padding:18px 20px;">${buildAssistantHtml(snapshot.payload.result || {}, snapshot.payload.topic || "")}</div>`;
  } else {
    $("snapshotPreview").innerHTML = `<div class="report-card" style="padding:18px 20px;"><p>当前快照类型暂不支持预览。</p></div>`;
  }
  schedulePanelRefresh($("snapshotPreview"));
}

function renderSnapshots() {
  if (!state.snapshots.length) {
    $("snapshotList").innerHTML = '<div class="panel dashboard-panel"><p>当前还没有保存的快照。你可以把看板、问答或自动报告保存下来，方便答辩时回放。</p></div>';
    $("snapshotPreview").innerHTML = "";
    return;
  }
  $("snapshotList").innerHTML = `
    <div class="panel dashboard-panel">
      <div class="section-header">
        <div>
          <div class="eyebrow">收藏与快照</div>
          <h3>本地已保存 ${state.snapshots.length} 份</h3>
        </div>
        <div class="section-meta">仅保存在当前浏览器</div>
      </div>
      <div class="snapshot-list">
        ${state.snapshots.map((item) => `
          <div class="snapshot-item">
            <div>
              <strong>${escapeHtml(item.title)}</strong>
              <div class="card-meta">${escapeHtml(item.type)} · ${escapeHtml(item.createdAt)}</div>
            </div>
            <div class="action-row">
              <button class="mini-button" type="button" data-snapshot-view="${escapeAttr(item.id)}">查看</button>
              <button class="mini-button danger" type="button" data-snapshot-delete="${escapeAttr(item.id)}">删除</button>
            </div>
          </div>
        `).join("")}
      </div>
    </div>
  `;
  $("snapshotList").querySelectorAll("[data-snapshot-view]").forEach((button) => {
    button.addEventListener("click", () => {
      const snapshot = state.snapshots.find((item) => item.id === button.dataset.snapshotView);
      renderSnapshotPreview(snapshot);
    });
  });
  $("snapshotList").querySelectorAll("[data-snapshot-delete]").forEach((button) => {
    button.addEventListener("click", () => {
      state.snapshots = state.snapshots.filter((item) => item.id !== button.dataset.snapshotDelete);
      persistSnapshots();
      renderSnapshots();
    });
  });
}

function scrollToBottom() { window.scrollTo({ top: document.body.scrollHeight, behavior: "smooth" }); }

function scrollPanelToTop(tabName, behavior = "smooth") {
  const panel = $(`${tabName}Tab`);
  if (!panel) return;
  panel.scrollIntoView({ behavior, block: "start" });
}

function appendMessage(role, html) {
  const wrapper = document.createElement("div");
  wrapper.className = `message ${role}`;
  wrapper.innerHTML = `<div class="message-card">${html}</div>`;
  $("chatMessages").appendChild(wrapper);
  state.history.push({ role, html });
  persistChatHistory();
  schedulePanelRefresh(wrapper);
  scrollToBottom();
  return wrapper;
}

function renderThinkingMessage() {
  const node = $("thinkingTemplate").content.firstElementChild.cloneNode(true);
  $("chatMessages").appendChild(node);
  let index = 0;
  node.querySelector("[data-stage]").textContent = stages[index];
  const timer = window.setInterval(() => {
    index = (index + 1) % stages.length;
    node.querySelector("[data-stage]").textContent = stages[index];
  }, 1200);
  scrollToBottom();
  return { destroy() { window.clearInterval(timer); node.remove(); } };
}

async function requestJson(url, payload) {
  const response = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!response.ok) throw new Error(await response.text() || `请求失败：${response.status}`);
  return response.json();
}

async function fetchJson(url) {
  const response = await fetch(url);
  if (!response.ok) throw new Error(await response.text() || `请求失败：${response.status}`);
  return response.json();
}

function buildAssistantHtml(result, question) {
  const chips = buildChips(result, question);
  const markdown = result.answer_markdown || result.report_markdown || "";
  const summary = extractSummary(markdown);
  const metrics = extractMetricCards(markdown);
  return `
    <div class="message-role">系统</div>
    ${chips.length ? `<div class="chip-row">${chips.map((chip) => `<span class="chip">${escapeHtml(chip)}</span>`).join("")}</div>` : ""}
    ${summary ? `<div class="summary-card"><div class="label">核心判断</div><div class="value">${renderMarkdownValue(summary)}</div></div>` : ""}
    ${renderMetricGrid(metrics)}
    <div class="markdown">${renderMarkdown(markdown)}</div>
    ${renderChart(result.chart_spec)}
    ${renderVizBlocks(result.viz_blocks)}
    ${renderSourceList(result.sources)}
    ${renderEvidencePanel(result)}
    ${renderSqlBlock(result.sql, "企业 SQL")}
    ${renderSqlBlock(result.macro_sql, "宏观 SQL")}
    ${renderTable(result.sql_rows, "结构化结果")}
    ${renderTable(result.macro_rows, "宏观结果")}
    ${result.warnings && result.warnings.length ? `<div class="detail-block"><strong>提示</strong><ul>${result.warnings.map((item) => `<li>${escapeHtml(item)}</li>`).join("")}</ul></div>` : ""}
  `;
}

function renderAdvancedToolSummary(toolResults = {}) {
  const equity = toolResults.equity || {};
  const equitySummary = equity.summary || {};
  const risk = toolResults.risk || {};
  const riskDimensions = risk.dimensions || {};
  const innovation = toolResults.innovation || {};
  const innovationDimensions = innovation.dimensions || {};
  const cards = [
    {
      label: "股权穿透",
      value: `${escapeHtml(String(equitySummary.node_count || 0))} 个节点`,
      meta: `${escapeHtml(String(equitySummary.edge_count || 0))} 条关系`,
    },
    {
      label: "风险雷达",
      value: `${escapeHtml(String(riskDimensions["风险事件总数"] || 0))} 个事件`,
      meta: `涉案金额 ${escapeHtml(formatCompactNumber(riskDimensions["涉案金额合计"]))}`,
    },
    {
      label: "创新指数",
      value: `${escapeHtml(String(innovationDimensions["专利总量"] || 0))} 项成果`,
      meta: `平均评分 ${escapeHtml(String(innovationDimensions["平均专利评分"] ?? "-"))}`,
    },
  ];
  return `
    <div class="advanced-summary-grid">
      ${cards.map((card) => `
        <div class="advanced-summary-card">
          <div class="label">${card.label}</div>
          <div class="value">${card.value}</div>
          <div class="card-meta">${card.meta}</div>
        </div>
      `).join("")}
    </div>
  `;
}

function renderAdvancedDetailPanels(toolResults = {}) {
  const equity = toolResults.equity || {};
  const risk = toolResults.risk || {};
  const innovation = toolResults.innovation || {};
  const riskDetails = (risk.details || []).slice(0, 3);
  const innovationDetails = (innovation.details || []).slice(0, 3);
  const panels = [
    {
      title: "股权结构摘要",
      body: equity.summary ? `已识别 ${escapeHtml(String(equity.summary.node_count || 0))} 个节点、${escapeHtml(String(equity.summary.edge_count || 0))} 条控制关系，适合用于展示集团层级和关键主体。`
        : "当前暂无股权结构摘要。",
    },
    {
      title: "重点风险提示",
      body: riskDetails.length
        ? riskDetails.map((item) => `${escapeHtml(item.risk_type || "未知风险")}｜${escapeHtml(item.filing_date || "-")}｜${escapeHtml(formatCompactNumber(item.amount_involved))}`).join("<br>")
        : "当前暂无重点风险事件。",
    },
    {
      title: "创新活跃概览",
      body: innovationDetails.length
        ? innovationDetails.map((item) => `${escapeHtml(String(item.application_year || "-"))}年 ${escapeHtml(item.patent_type || "未知类型")} ${escapeHtml(String(item.patent_count || 0))} 项，均分 ${escapeHtml(String(item.avg_score ?? "-"))}`).join("<br>")
        : "当前暂无创新维度数据。",
    },
  ];
  return `
    <div class="advanced-panel-grid">
      ${panels.map((panel) => `
        <div class="advanced-panel">
          <strong>${escapeHtml(panel.title)}</strong>
          <div class="advanced-panel-body">${panel.body}</div>
        </div>
      `).join("")}
    </div>
  `;
}

function renderAdvancedSources(sources = []) {
  if (!sources.length) return "";
  return `
    <details class="detail-block advanced-source-toggle">
      <summary>查看工具来源与原始片段</summary>
      ${renderSourceList(sources)}
    </details>
  `;
}

function buildAdvancedHtml(result, question) {
  const companyName = $("companySelect")?.value || "";
  const years = [...new Set((question.match(/20\d{2}/g) || []).map((item) => `${item}年`))];
  const chips = [companyName, "高级分析", "股权图谱", "风险雷达", "创新指数", ...years].filter(Boolean).slice(0, 6);
  const markdown = result.answer_markdown || "";
  const summary = extractSummary(markdown);
  return `
    <div class="message-role">高级分析</div>
    ${chips.length ? `<div class="chip-row">${chips.map((chip) => `<span class="chip">${escapeHtml(chip)}</span>`).join("")}</div>` : ""}
    ${summary ? `<div class="summary-card"><div class="label">综合结论</div><div class="value">${renderMarkdownValue(summary)}</div></div>` : ""}
    ${renderAdvancedToolSummary(result.tool_results || {})}
    <div class="markdown">${renderMarkdown(markdown)}</div>
    ${renderAdvancedDetailPanels(result.tool_results || {})}
    ${renderAdvancedVizBlocks(result.viz_blocks || [])}
    ${renderAdvancedSources(result.sources || [])}
  `;
}

function renderWhiteboxHtml(result) {
  const chunks = (result.chunks || []).map((chunk, index) => `
    <details class="source-item" open>
      <summary><span class="source-index">${index + 1}</span><span>${escapeHtml(chunk.metadata?.source || "未知来源")} / 第 ${escapeHtml(String(chunk.metadata?.page ?? "?"))} 页</span></summary>
      <div class="source-snippet">${escapeHtml(chunk.text || "")}</div>
    </details>
  `).join("");
  return `
    <div class="report-card" style="padding:18px 20px;">
      <div class="message-role">白盒示例</div>
      <div class="summary-card">
        <div class="label">透明解释</div>
        <div class="value">把答案、SQL、原文切片和 reasoning 分层展开，适合比赛答辩演示可追溯能力。</div>
      </div>
      <div class="markdown">${renderMarkdown(result.answer_markdown || "")}</div>
      <div class="detail-block">
        <div class="detail-title">
          <strong>执行 SQL</strong>
          <span class="detail-tag">结构化证据</span>
        </div>
        <pre>${escapeHtml(result.sql || "")}</pre>
      </div>
      <div class="whitebox-columns">
        <div>
          <div class="detail-block" style="border-top:0;padding-top:0;">
            <div class="detail-title">
              <strong>RAG 原文切片</strong>
              <span class="detail-tag">非结构化证据</span>
            </div>
          </div>
          <div class="source-list">${chunks}</div>
        </div>
        <div>
          <div class="detail-block" style="border-top:0;padding-top:0;">
            <div class="detail-title">
              <strong>推理说明</strong>
              <span class="detail-tag">解释层</span>
            </div>
          </div>
          <div class="summary-card" style="margin-top:10px;"><div class="value">${renderMarkdown(result.reasoning_markdown || "")}</div></div>
        </div>
      </div>
    </div>
  `;
}

function setActiveTab(tabName) {
  document.querySelectorAll(".tab").forEach((tab) => tab.classList.toggle("active", tab.dataset.tab === tabName));
  document.querySelectorAll(".tab-panel").forEach((panel) => panel.classList.toggle("active", panel.id === `${tabName}Tab`));
  const activeTab = document.querySelector(`.tab[data-tab="${tabName}"]`);
  if (activeTab) {
    activeTab.scrollIntoView({ behavior: "smooth", block: "nearest", inline: "center" });
  }
  const activePanel = $(`${tabName}Tab`);
  if (activePanel) schedulePanelRefresh(activePanel);
  if (tabName === "project" && activePanel) {
    window.requestAnimationFrame(() => playProjectReveal(activePanel));
  } else {
    clearProjectRevealTimers();
  }
  if (tabName === "database") {
    void loadDatabaseCatalog().catch((error) => {
      $("databaseCatalog").innerHTML = `<div class="panel dashboard-panel"><p>${escapeHtml(error.message)}</p></div>`;
      $("databasePreview").innerHTML = "";
    });
  }
}

async function bootstrap() {
  const data = await fetchJson("/api/bootstrap");
  state.deepseekEnabled = Boolean(data.deepseek_enabled);
  state.industries = data.industries || [];
  state.companies = data.companies || [];
  state.years = data.years || [];
  state.stats = data.stats || {};
  $("modePill").textContent = state.deepseekEnabled ? "DeepSeek 增强模式" : "本地检索模式";
  $("industrySelect").insertAdjacentHTML("beforeend", (data.industries || []).map((name) => `<option value="${escapeHtml(name)}">${escapeHtml(name)}</option>`).join(""));
  $("companySelect").insertAdjacentHTML("beforeend", (data.companies || []).map((name) => `<option value="${escapeHtml(name)}">${escapeHtml(name)}</option>`).join(""));
  $("compareCompanySelect").insertAdjacentHTML("beforeend", (data.companies || []).map((name) => `<option value="${escapeHtml(name)}">${escapeHtml(name)}</option>`).join(""));
  $("yearSelect").insertAdjacentHTML("beforeend", (data.years || []).map((year) => `<option value="${year}">${year}</option>`).join(""));
  $("stats").innerHTML = [["企业数", data.stats.companies], ["文档数", data.stats.documents], ["财务事实", data.stats.financial_facts], ["宏观事实", data.stats.macro_facts]].map(([label, value]) => `<div class="stat"><div class="label">${label}</div><div class="value">${value ?? "-"}</div></div>`).join("");
}

async function loadDashboard() {
  const params = new URLSearchParams();
  if ($("industrySelect").value) params.set("industry_name", $("industrySelect").value);
  if ($("companySelect").value) params.set("company_name", $("companySelect").value);
  if ($("yearSelect").value) params.set("report_year", $("yearSelect").value);
  params.set("ranking_scope", $("rankingScopeSelect").value || "industry");
  const payload = await fetchJson(`/api/dashboard${params.toString() ? `?${params.toString()}` : ""}`);
  state.dashboard = payload;
  renderDashboard(payload);
}

async function loadProfile() {
  const params = new URLSearchParams();
  if ($("companySelect").value) params.set("company_name", $("companySelect").value);
  if ($("yearSelect").value) params.set("report_year", $("yearSelect").value);
  const payload = await fetchJson(`/api/profile${params.toString() ? `?${params.toString()}` : ""}`);
  state.profile = payload;
  $("profileDashboard").innerHTML = renderProfileOverview(payload);
  schedulePanelRefresh($("profileTab"));
}

async function loadCompare() {
  const params = new URLSearchParams();
  if ($("companySelect").value) params.set("company_name", $("companySelect").value);
  if ($("compareCompanySelect").value) params.set("compare_company_name", $("compareCompanySelect").value);
  if ($("yearSelect").value) params.set("report_year", $("yearSelect").value);
  const payload = await fetchJson(`/api/compare${params.toString() ? `?${params.toString()}` : ""}`);
  state.compare = payload;
  $("comparePrimaryCompany").textContent = $("companySelect").value || "跟随左侧企业选择";
  $("compareDashboard").innerHTML = renderCompareOverview(payload);
  schedulePanelRefresh($("compareTab"));
}

async function loadTimeline() {
  const params = new URLSearchParams();
  if ($("companySelect").value) params.set("company_name", $("companySelect").value);
  const payload = await fetchJson(`/api/timeline${params.toString() ? `?${params.toString()}` : ""}`);
  state.timeline = payload;
  $("timelineDashboard").innerHTML = renderTimelineOverview(payload);
  schedulePanelRefresh($("timelineTab"));
}

function attachDatabaseCatalogEvents() {
  $("databaseCatalog")?.querySelectorAll("[data-database-table]").forEach((button) => {
    button.addEventListener("click", async () => {
      state.databaseSelectedTable = button.dataset.databaseTable || "";
      syncDatabaseTableSelect();
      await loadDatabasePreview(state.databaseSelectedTable, true);
    });
  });
  $("databaseCatalog")?.querySelectorAll("[data-database-category]").forEach((button) => {
    button.addEventListener("click", () => {
      state.databaseCategory = button.dataset.databaseCategory || "all";
      refreshDatabaseCatalogView();
    });
  });
}

function attachDatabasePreviewEvents() {
  $("databasePreview")?.querySelectorAll("[data-scroll-left]").forEach((button) => {
    button.addEventListener("click", () => {
      const host = document.getElementById(button.dataset.scrollLeft || "");
      if (host) host.scrollBy({ left: -280, behavior: "smooth" });
    });
  });
  $("databasePreview")?.querySelectorAll("[data-scroll-right]").forEach((button) => {
    button.addEventListener("click", () => {
      const host = document.getElementById(button.dataset.scrollRight || "");
      if (host) host.scrollBy({ left: 280, behavior: "smooth" });
    });
  });
}

function refreshDatabaseCatalogView() {
  if ($("databaseSearchInput")) {
    $("databaseSearchInput").value = state.databaseSearch || "";
  }
  $("databaseCatalog").innerHTML = renderDatabaseCatalog(state.databaseCatalog || { tables: [] });
  attachDatabaseCatalogEvents();
}

async function loadDatabaseCatalog(force = false) {
  if (!force && state.databaseCatalog) {
    syncDatabaseTableSelect();
    refreshDatabaseCatalogView();
    if (state.databaseSelectedTable) {
      await loadDatabasePreview(state.databaseSelectedTable, false);
    }
    return;
  }
  $("databaseCatalog").innerHTML = '<div class="panel dashboard-panel"><p>正在加载数据库目录...</p></div>';
  const payload = await fetchJson("/api/database/catalog");
  state.databaseCatalog = payload;
  const availableTables = payload.table_names || [];
  state.databaseSelectedTable = availableTables.includes(state.databaseSelectedTable)
    ? state.databaseSelectedTable
    : (availableTables[0] || "");
  syncDatabaseTableSelect();
  refreshDatabaseCatalogView();
  if (state.databaseSelectedTable) {
    await loadDatabasePreview(state.databaseSelectedTable, true);
  } else {
    $("databasePreview").innerHTML = '<div class="panel dashboard-panel"><p>当前没有可预览的数据表。</p></div>';
  }
}

async function loadDatabasePreview(tableName = state.databaseSelectedTable, force = false) {
  const resolvedTable = tableName || state.databaseSelectedTable;
  if (!resolvedTable) {
    $("databasePreview").innerHTML = '<div class="panel dashboard-panel"><p>请选择一个数据表后查看预览。</p></div>';
    return;
  }
  const limit = Number($("databaseLimitSelect")?.value || 20);
  if (!force && state.databasePreview?.table_name === resolvedTable && Number(state.databasePreview?.limit || 0) === limit) {
    $("databasePreview").innerHTML = renderDatabasePreview(state.databasePreview);
    attachDatabasePreviewEvents();
    schedulePanelRefresh($("databaseTab"));
    return;
  }
  state.databaseSelectedTable = resolvedTable;
  syncDatabaseTableSelect();
  refreshDatabaseCatalogView();
  $("databasePreview").innerHTML = '<div class="panel dashboard-panel"><p>正在加载表结构与示例数据...</p></div>';
  const payload = await fetchJson(`/api/database/table?table_name=${encodeURIComponent(resolvedTable)}&limit=${encodeURIComponent(limit)}`);
  state.databasePreview = payload;
  $("databasePreview").innerHTML = renderDatabasePreview(payload);
  attachDatabasePreviewEvents();
  refreshDatabaseCatalogView();
  schedulePanelRefresh($("databaseTab"));
}

function openPrintableWindow(title, bodyHtml) {
  const win = window.open("", "_blank", "noopener,noreferrer");
  if (!win) return;
  win.document.write(`
    <!doctype html>
    <html lang="zh-CN">
      <head>
        <meta charset="utf-8" />
        <title>${escapeHtml(title)}</title>
        <style>
          body { font-family: "PingFang SC", "Helvetica Neue", sans-serif; margin: 32px; color: #0f172a; line-height: 1.75; }
          h1, h2, h3 { margin: 0 0 12px; }
          .report-card, .summary-card, .metric-card, .source-item, .detail-block, .table-box { break-inside: avoid; }
          table { width: 100%; border-collapse: collapse; margin-top: 12px; }
          th, td { border-bottom: 1px solid #e2e8f0; padding: 8px 10px; text-align: left; }
        </style>
      </head>
      <body>${bodyHtml}</body>
    </html>
  `);
  win.document.close();
  win.focus();
  win.print();
}

async function reloadCorePanels() {
  await loadDashboard();
  await loadProfile();
  await loadCompare();
  await loadTimeline();
  renderShowcase();
}

async function applyShowcaseScene(sceneId, options = {}) {
  const scene = getShowcaseScene(sceneId);
  state.showcaseSceneId = scene.id;
  if (scene.companyName) $("companySelect").value = scene.companyName;
  if (scene.reportYear) $("yearSelect").value = scene.reportYear;
  if (scene.compareCompanyName) $("compareCompanySelect").value = scene.compareCompanyName;
  if (scene.quickPrompt) {
    $("chatInput").value = scene.quickPrompt;
    $("workflowInput").value = scene.quickPrompt.includes("生成") ? scene.quickPrompt : $("workflowInput").value;
  }
  $("comparePrimaryCompany").textContent = $("companySelect").value || "跟随左侧企业选择";
  await reloadCorePanels();
  const targetTab = options.keepShowcase ? "showcase" : scene.tab;
  setActiveTab(targetTab);
  if (!options.run) {
    scrollPanelToTop(targetTab, options.keepShowcase ? "auto" : "smooth");
    return;
  }
  if (scene.id === "auto-report") {
    $("workflowInput").value = scene.quickPrompt || $("workflowInput").value;
    setActiveTab("workflow");
    await handleWorkflowSubmit();
    return;
  }
  if (scene.id === "whitebox-trace") {
    setActiveTab("whitebox");
    scrollToBottom();
    return;
  }
  setActiveTab("chat");
  await handleChatSubmit(scene.quickPrompt || $("chatInput").value);
}

async function handleChatSubmit(question) {
  const trimmed = enrichFollowupQuestion(question);
  if (!trimmed) return;
  appendMessage("user", `<div class="message-role">你</div><div class="markdown"><p>${escapeHtml(trimmed)}</p></div>`);
  $("chatInput").value = "";
  const thinking = renderThinkingMessage();
  try {
    const result = await requestJson("/api/chat", {
      question: trimmed,
      company_name: $("companySelect").value || null,
      industry_name: $("industrySelect").value || null,
      report_year: $("yearSelect").value ? Number($("yearSelect").value) : null,
      top_k: Number($("topKInput").value),
    });
    thinking.destroy();
    inferChatContext(trimmed, result);
    state.lastChatResult = result;
    state.lastChatQuestion = trimmed;
    appendMessage("assistant", buildAssistantHtml(result, trimmed));
    renderFollowups(buildFollowups(result));
    renderShowcase();
  } catch (error) {
    thinking.destroy();
    appendMessage("assistant", `<div class="message-role">系统</div><div class="markdown"><p>${escapeHtml(error.message)}</p></div>`);
    renderFollowups([]);
  }
}

async function handleWorkflowSubmit() {
  const topic = $("workflowInput").value.trim();
  if (!topic) return;
  $("workflowResult").innerHTML = `<div class="report-card" style="padding:18px 20px;"><div class="thinking-title">正在生成自动化报告</div><div class="thinking-stage">系统正在执行真实 SQL 检索、向量检索并整理最终研报。</div><div class="thinking-bar"><span></span></div></div>`;
  scrollToBottom();
  try {
    const result = await requestJson("/api/workflow", {
      topic,
      company_name: $("companySelect").value || null,
      industry_name: $("industrySelect").value || null,
      report_year: $("yearSelect").value ? Number($("yearSelect").value) : null,
      top_k: Number($("topKInput").value),
    });
    state.lastWorkflowMarkdown = result.report_markdown || "";
    state.lastWorkflowTitle = topic;
    state.lastWorkflowHtml = buildAssistantHtml(result, topic);
    $("workflowResult").innerHTML = `<div class="report-card" style="padding:18px 20px;">${state.lastWorkflowHtml}</div>`;
    schedulePanelRefresh($("workflowResult"));
    renderShowcase();
    scrollToBottom();
  } catch (error) {
    $("workflowResult").innerHTML = `<div class="report-card" style="padding:18px 20px;"><p>${escapeHtml(error.message)}</p></div>`;
  }
}

function parseBatchCompanies() {
  const raw = $("batchCompaniesInput").value || "";
  const items = raw.split(/[\n,，、]+/).map((item) => item.trim()).filter(Boolean);
  if (!items.length && $("companySelect").value) return [$("companySelect").value];
  return [...new Set(items)].slice(0, 5);
}

async function handleBatchWorkflowSubmit() {
  const companyNames = parseBatchCompanies();
  if (!companyNames.length) {
    $("workflowResult").innerHTML = `<div class="report-card" style="padding:18px 20px;"><p>请先在左侧选择企业，或在批量公司名单中输入至少一个公司名。</p></div>`;
    return;
  }
  $("workflowResult").innerHTML = `<div class="report-card" style="padding:18px 20px;"><div class="thinking-title">正在批量生成自动化报告</div><div class="thinking-stage">系统将逐家公司执行真实检索并汇总成一份总报告。</div><div class="thinking-bar"><span></span></div></div>`;
  try {
    const result = await requestJson("/api/batch-workflow", {
      company_names: companyNames,
      industry_name: $("industrySelect").value || null,
      report_year: $("yearSelect").value ? Number($("yearSelect").value) : null,
      top_k: Number($("topKInput").value),
    });
    state.lastWorkflowMarkdown = result.combined_markdown || "";
    state.lastWorkflowTitle = `batch-${companyNames.join("-")}`;
    state.lastWorkflowHtml = `
      <div class="summary-card">
        <div class="label">批量报告摘要</div>
        <div class="value">已生成 ${escapeHtml(String((result.items || []).length))} 家公司的自动化报告，支持继续下载 Markdown 或导出 PDF。</div>
      </div>
      ${(result.items || []).map((item) => `
        <div class="detail-block">
          <div class="detail-title">
            <strong>${escapeHtml(item.company_name)}</strong>
            <span class="detail-tag">${escapeHtml(item.data_mode || "hybrid")}</span>
          </div>
          <div class="markdown">${renderMarkdown(item.report_markdown || "")}</div>
          ${item.warnings && item.warnings.length ? `<ul>${item.warnings.map((warning) => `<li>${escapeHtml(warning)}</li>`).join("")}</ul>` : ""}
        </div>
      `).join("")}
    `;
    $("workflowResult").innerHTML = `<div class="report-card" style="padding:18px 20px;">${state.lastWorkflowHtml}</div>`;
    schedulePanelRefresh($("workflowResult"));
    renderShowcase();
    scrollToBottom();
  } catch (error) {
    $("workflowResult").innerHTML = `<div class="report-card" style="padding:18px 20px;"><p>${escapeHtml(error.message)}</p></div>`;
  }
}

async function handleAdvancedSubmit() {
  const question = $("advancedInput").value.trim();
  const companyName = $("companySelect").value;
  if (!question || !companyName) {
    $("advancedResult").innerHTML = `<div class="report-card" style="padding:18px 20px;"><p>请先在左侧选择企业，再发起高级分析。</p></div>`;
    return;
  }
  $("advancedNodeDetail").innerHTML = "";
  $("advancedResult").innerHTML = `<div class="report-card" style="padding:18px 20px;"><div class="thinking-title">正在生成高级分析</div><div class="thinking-stage">系统正在整理股权图谱、风险雷达和创新指数。</div><div class="thinking-bar"><span></span></div></div>`;
  try {
    const result = await requestJson("/api/advanced", {
      question,
      company_name: companyName,
    });
    $("advancedResult").innerHTML = `<div class="report-card" style="padding:18px 20px;">${buildAdvancedHtml(result, question)}</div>`;
    schedulePanelRefresh($("advancedResult"));
    scrollToBottom();
  } catch (error) {
    $("advancedResult").innerHTML = `<div class="report-card" style="padding:18px 20px;"><p>${escapeHtml(error.message)}</p></div>`;
  }
}

function downloadWorkflowMarkdown() {
  if (!state.lastWorkflowMarkdown) {
    $("workflowResult").innerHTML = `<div class="report-card" style="padding:18px 20px;"><p>请先生成一次自动化报告，再下载 Markdown。</p></div>`;
    return;
  }
  const blob = new Blob([state.lastWorkflowMarkdown], { type: "text/markdown;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = buildFilename(state.lastWorkflowTitle || "deep_diagnostic_report", "md");
  anchor.click();
  URL.revokeObjectURL(url);
}

function exportWorkflowPdf() {
  if (!state.lastWorkflowHtml) {
    $("workflowResult").innerHTML = `<div class="report-card" style="padding:18px 20px;"><p>请先生成一次自动化报告，再导出 PDF。</p></div>`;
    return;
  }
  openPrintableWindow(state.lastWorkflowTitle || "deep_diagnostic_report", `<h1>${escapeHtml(state.lastWorkflowTitle || "自动化报告")}</h1>${state.lastWorkflowHtml}`);
}

async function loadWhitebox() {
  const response = await fetch("/api/whitebox");
  const result = await response.json();
  $("whiteboxResult").innerHTML = renderWhiteboxHtml(result);
  schedulePanelRefresh($("whiteboxResult"));
}

document.addEventListener("DOMContentLoaded", async () => {
  await bootstrap();
  renderProjectOverview();
  await applyShowcaseScene(state.showcaseSceneId, { run: false, keepShowcase: true });
  restoreChatHistory();
  restoreSnapshots();
  renderSnapshots();
  $("topKInput").addEventListener("input", (event) => { $("topKValue").textContent = event.target.value; });
  document.querySelectorAll(".tab").forEach((tab) => tab.addEventListener("click", () => setActiveTab(tab.dataset.tab)));
  document.querySelectorAll(".quick-question").forEach((button) => button.addEventListener("click", () => {
    setActiveTab("chat");
    $("chatInput").value = button.dataset.question;
    $("chatInput").focus();
  }));
  $("clearHistoryButton").addEventListener("click", clearChatHistory);
  $("industrySelect").addEventListener("change", async () => { await reloadCorePanels(); });
  $("companySelect").addEventListener("change", async () => {
    $("comparePrimaryCompany").textContent = $("companySelect").value || "跟随左侧企业选择";
    await reloadCorePanels();
  });
  $("yearSelect").addEventListener("change", async () => {
    await reloadCorePanels();
  });
  $("rankingScopeSelect").addEventListener("change", async () => { await loadDashboard(); renderShowcase(); });
  $("compareCompanySelect").addEventListener("change", async () => { await loadCompare(); renderShowcase(); });
  $("compareRefreshButton").addEventListener("click", async () => { await loadCompare(); renderShowcase(); });
  $("databaseTableSelect").addEventListener("change", async (event) => {
    state.databaseSelectedTable = event.target.value || "";
    await loadDatabasePreview(state.databaseSelectedTable, true);
  });
  $("databaseLimitSelect").addEventListener("change", async () => {
    await loadDatabasePreview(state.databaseSelectedTable, true);
  });
  $("databaseSearchInput").addEventListener("input", (event) => {
    state.databaseSearch = event.target.value || "";
    refreshDatabaseCatalogView();
  });
  $("databaseRefreshButton").addEventListener("click", async () => {
    await loadDatabaseCatalog(true);
  });
  $("chatForm").addEventListener("submit", async (event) => { event.preventDefault(); await handleChatSubmit($("chatInput").value); });
  $("chatInput").addEventListener("keydown", async (event) => {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      await handleChatSubmit($("chatInput").value);
    }
  });
  $("workflowButton").addEventListener("click", handleWorkflowSubmit);
  $("batchWorkflowButton").addEventListener("click", handleBatchWorkflowSubmit);
  $("workflowDownloadButton").addEventListener("click", downloadWorkflowMarkdown);
  $("workflowPdfButton").addEventListener("click", exportWorkflowPdf);
  $("advancedButton").addEventListener("click", handleAdvancedSubmit);
  $("saveDashboardSnapshotButton").addEventListener("click", () => {
    if (state.dashboard) saveSnapshot("dashboard", `运营看板快照 ${formatNowLabel()}`, state.dashboard);
  });
  $("saveChatSnapshotButton").addEventListener("click", () => {
    if (state.lastChatResult) saveSnapshot("chat", state.lastChatQuestion || `问答快照 ${formatNowLabel()}`, { question: state.lastChatQuestion, result: state.lastChatResult });
  });
  $("saveWorkflowSnapshotButton").addEventListener("click", () => {
    if (state.lastWorkflowMarkdown) saveSnapshot("workflow", state.lastWorkflowTitle || `报告快照 ${formatNowLabel()}`, { topic: state.lastWorkflowTitle, result: { report_markdown: state.lastWorkflowMarkdown, sources: [], warnings: [] } });
  });
  if (!state.history.length) {
    appendMessage("assistant", `<div class="message-role">系统</div><div class="summary-card"><div class="label">欢迎使用</div><div class="value">现在已经切到自建网页版本。你可以直接提企业诊断、双公司对比或宏观联动问题。</div></div>`);
  }
  await loadWhitebox();
  window.addEventListener("resize", () => {
    const activePanel = document.querySelector(".tab-panel.active");
    if (activePanel) resizeCharts(activePanel);
  }, { passive: true });
  schedulePanelRefresh(document.querySelector(".tab-panel.active") || $("showcaseTab"));
  if ($("projectTab")?.classList.contains("active")) {
    playProjectReveal($("projectTab"));
  }
  renderShowcase();
  renderFollowups([]);
});
