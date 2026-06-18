# 前端构建说明（Claude-design 重设计版 → FastAPI 同源托管）

本目录把 Claude design 产出的单文件 bundle（`~/Downloads/DeepInsight.html`）转成可由
FastAPI 在根路径同源托管的静态前端，并把每个页面接到现有 `/api/*` 后端。

## 产物（写入 `webapp/static/`）
- `index.html` —— SPA 入口（由 `GET /` 以 `no-store` 提供）。
- `dc-runtime.js` —— Claude design 的 DC/React 运行时（从 CDN 加载 React UMD）。
- `fonts/<uuid>.woff2` —— 114 个字体子集，CSS 内以 `/static/fonts/...` 引用。
- `LineChart.dc.html` / `BarChart.dc.html` —— 自写的图表组件（运行时按 `name` 取
  `/static/<name>.dc.html`；`dc-runtime.js` 里 `COMPONENT_DIR` 已改为 `/static`）。
- `_legacy_native/` —— 旧版原生 JS 前端备份（index/app.js/styles.css），未删除。

## 源文件（本目录）
- `extract.py` —— 一次性：从 bundle 解出字体/runtime/模板，生成 `template.html`（已把字体与
  runtime 的 URL 改写为 `/static/...`，并把组件类替换为 `/*__COMPONENT__*/` 占位）和
  `component.orig.js`（原始组件，仅作参考）。
- `repair_tables.py` —— 一次性：修复 bundle 在打包时把 `<sc-for>`/`<sc-if>` 从 `<table>`
  里「foster-parent」出去导致的 4 处表格（对比矩阵 / 数据库预览 / 智能问答证据 / 白盒 SQL）。
  **已对 `template.html` 应用过，无需再次运行。**
- `component.js` —— **可编辑的组件**，在原始组件上注入了 `/api` 数据层（见下）。
- `build.py` —— 把 `component.js` 注入 `template.html` 占位符，输出 `static/index.html`。

## 改前端后如何重建
```bash
# 只改 component.js（数据层/适配器），然后：
python3 webapp/frontend_src/build.py
```

## 数据层要点（component.js）
- `componentDidMount` → `loadBootstrap()`（下拉/统计/DeepSeek 开关，并据真实公司/年份校正默认值）
  + `loadPage()`（按当前页拉取对应 `/api/*`）。
- 公司/年份/口径切换、页面切换都会触发 `loadPage()` 重新拉数。
- 响应存入 `state.api`，按 `company|year|scope` 做 key 校验（`_matched`），**命中才用 live，
  否则回退到设计自带的演示数据**——所以无数据库/接口报错时 UI 仍完整可看。
- 各 `*Vals()` 仅改「取数来源」，输出键/样式与原设计完全一致；字段名严格按 `webapp/main.py`
  的 snake_case（见 `frontend-redesign-handoff/02-API_CONTRACT.md`）。
- chat / workflow / batch-workflow / advanced 为 POST：成功用 live，失败回退演示答案。

## 本地自测
```bash
make web   # uvicorn webapp.main:app --port 8000
```
需要真实数据时数据库在 `data/enterprise_analysis.db`（线上服务器已有真实库，勿覆盖）。
