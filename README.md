# 智能体赋能的企业运营分析与决策支持系统

本项目是面向 2026 年中国大学生计算机设计大赛大数据主题赛的参赛作品原型，聚焦医药生物领域，融合关系数据库、向量库、多角色智能体、宏观数据联动、白盒溯源与自动化报告生成，构建可展示、可交互、可追溯的企业运营分析与决策支持系统。

## 作品能力

- 企业财务与年报问答：基于 SQLite + Chroma 进行本地检索与证据整合
- 多角色分析：支持投资者、管理者、监管机构三种视角
- 双公司比较：支持同年经营差异对比与可视化柱状图
- 企业 + 宏观联动：支持国家统计局卫生数据与企业经营环境联动分析
- 白盒溯源：可展示 SQL、宏观 SQL、RAG 原文切片与 reasoning 面板
- 自动化报告：支持一键生成结构化 Markdown 报告

## 推荐演示入口

比赛展示主页面：

```bash
streamlit run scripts/streamlit/system_console.py
```

也可以直接使用：

```bash
make run
```

推荐演示顺序：

1. 企业诊断
2. 双公司比较
3. 企业与宏观联动分析
4. 白盒溯源
5. 自动化报告

系统中已内置“比赛演示快捷入口”，可直接一键启动上述场景。

## 自建网页版

当前仓库已新增基于 `FastAPI` 的自建网页版本，用来替代 Streamlit 主问答页并继续向比赛展示版网页演进。

启动方式：

```bash
uvicorn webapp.main:app --reload --host 0.0.0.0 --port 8000
```

或：

```bash
make web
```

打开地址：

```text
http://localhost:8000
```

当前网页版已支持：

- 答辩模式首页：默认给出演示顺序、场景脚本、一键切场景、全屏与大屏展示
- ChatGPT 风格主问答页面
- 运营看板：导入结果看板、财务趋势卡、行业横向排名、预警中心、宏观联动
- 公司 360 画像页：财务、风险、创新、股权结构联动展示
- 对比矩阵页：双公司核心指标、风险和专利对比
- 事件时间轴页：财务、风险、创新事件串联
- 自动化报告页面：支持单公司生成、批量生成、Markdown 下载与浏览器打印导出 PDF
- 收藏与快照：可把看板、问答、报告保存到本地浏览器，方便答辩回放
- 企业/行业/年份筛选
- 医药细分赛道行业筛选与同级行业排名
- 关键指标卡片、来源折叠、证据定位、简单图表展示

## 演示缓存 JSON

为了让比赛演示和测试运行更快，项目已支持将主要功能预计算为本地 JSON 缓存：

```bash
python3 -m deepinsight.demo.demo_cache
```

或：

```bash
make cache
```

生成目录：

```text
demo_cache/
```

当前缓存覆盖：

- 企业诊断预设问题
- 双公司比较预设问题
- 企业与宏观联动预设问题
- 自动化报告默认主题
- 高级分析默认问题
- 白盒溯源示例

在比赛主页面侧边栏中打开 `演示极速模式` 后，命中这些预设问题会优先读取本地 JSON，而不是实时重新计算。

## 安装依赖

```bash
python3 -m pip install -r requirements.txt
```

## 初始化数据

```bash
python3 -m deepinsight.dataops.db_init
python3 -m deepinsight.dataops.db_expand
python3 -m deepinsight.dataops.data_pipeline
```

当前 `deepinsight.dataops.data_pipeline` 会默认优先导入 [Final_md](/Volumes/ORICO/code1/Final_md)，并递归扫描“按公司名分文件夹”的完整版研报目录结构；如果需要，也可以通过 `--input-dir` 显式指定其他目录。

出于仓库体积控制考虑，完整版 `Final_md/` 语料目录、本地归档压缩包以及审计生成的 CSV 默认不纳入 Git 仓库；上传到 GitHub 时保留代码与说明，语料文件请在本地自行放置。

当前导入链路还支持：

- 同公司同年份新版文档替换后，自动清理旧版向量与财务事实
- 文件未变化时自动跳过，支持断点续跑
- `SQLite WAL + busy_timeout`，避免并发导入时出现 `database is locked`
- `--force` 强制重跑指定目录或文件
- 表格、堆叠式财务摘要、显式指标行三类财务事实抽取
- 对“只有图片占位、没有正文”的 Markdown 做空文本识别，不再写入占位 chunks，并在导入输出中标记 `状态=源文档无可抽取正文`

如果需要在导入前先扫描源文件质量，可以执行：

```bash
python3 -m deepinsight.dataops.data_pipeline --input-dir /Volumes/ORICO/code1/Final_md --audit-text-quality --audit-output /Volumes/ORICO/code1/audit_md/final_md_text_quality.csv
```

其中 `--min-text-ratio` 可调整风险阈值，默认 `5%`。

如果需要为现有公司回填医药行业与细分赛道标签，可以执行：

```bash
python3 -m deepinsight.dataops.data_pipeline --backfill-industries
```

## 导入宏观数据

项目支持将国家统计局卫生类 Excel 直接导入 `fact_macro_data`：

```bash
python3 -m deepinsight.dataops.macro_import --excel-path "/Volumes/ORICO/code1/data/raw_macro/国家统计局_卫生_2022_2024.xlsx"
```

## 主要页面

基础问答页：

```bash
streamlit run scripts/streamlit/chat_console.py
```

统一系统页：

```bash
streamlit run scripts/streamlit/system_console.py
```

可选页面：

```bash
streamlit run scripts/streamlit/analysis_studio.py
streamlit run scripts/streamlit/report_studio.py
```

## 测试

项目当前已补充一套基础冒烟测试，覆盖：

- 数据库与 Chroma 可用性
- 主问答链路
- 自动化报告链路
- 高级分析链路
- 演示缓存 JSON 完整性

运行方式：

```bash
python3 -m unittest discover -s tests -v
```

或：

```bash
make test
```

## 环境变量

启用 DeepSeek 增强模式时：

```bash
export DEEPSEEK_API_KEY=your_key
export DEEPSEEK_MODEL=deepseek-chat
```

未配置 `DEEPSEEK_API_KEY` 时，系统会进入本地降级模式，但仍可使用：

- 本地财务问答
- 宏观问答
- 双公司比较
- 企业与宏观联动

## 降级说明

- 未配置 `DEEPSEEK_API_KEY` 时，部分页面会进入本地降级模式。
- 未准备好 Chroma 数据或依赖时，向量检索相关能力会部分不可用。
- 自动化研报页在无 key 时会输出结构化本地结果，而不是完整 LLM 生成报告。

## 代码结构

当前仓库已经按功能整理为更接近成品项目的结构，顶层主要保留配置、数据目录和项目说明；Streamlit 启动脚本统一收纳在 `scripts/streamlit/`，主要实现代码归档在 `deepinsight/` 包下：

- [deepinsight/apps](/Volumes/ORICO/code1/deepinsight/apps): Streamlit 页面与比赛主入口
- [deepinsight/core](/Volumes/ORICO/code1/deepinsight/core): 检索、缓存、图谱工具与通用 UI 组件
- [deepinsight/dataops](/Volumes/ORICO/code1/deepinsight/dataops): 数据入库、数据库初始化与图谱扩展脚本
- [deepinsight/demo](/Volumes/ORICO/code1/deepinsight/demo): 演示缓存 JSON 构建逻辑
- [deepinsight/experiments](/Volumes/ORICO/code1/deepinsight/experiments): 非主链路实验代码
- [deepinsight/config.py](/Volumes/ORICO/code1/deepinsight/config.py): 统一路径与项目级配置
- [scripts/streamlit](/Volumes/ORICO/code1/scripts/streamlit): Streamlit 页面启动脚本
- [scripts/README.md](/Volumes/ORICO/code1/scripts/README.md): 启动方式说明
- [webapp](/Volumes/ORICO/code1/webapp): 自建网页版本
- [demo_cache](/Volumes/ORICO/code1/demo_cache): 已生成的演示缓存 JSON
- [audit_md](/Volumes/ORICO/code1/audit_md): 项目审查与问题记录文档
- [assets](/Volumes/ORICO/code1/assets): 图片等静态资源
- [data/raw_macro](/Volumes/ORICO/code1/data/raw_macro): 宏观原始 Excel 数据
- [data/archives](/Volumes/ORICO/code1/data/archives): 原始压缩包与归档文件

常用启动入口：

- [system_console.py](/Volumes/ORICO/code1/scripts/streamlit/system_console.py): 比赛展示主入口
- [chat_console.py](/Volumes/ORICO/code1/scripts/streamlit/chat_console.py): 基础问答入口
- [analysis_studio.py](/Volumes/ORICO/code1/scripts/streamlit/analysis_studio.py): 高级分析入口
- [report_studio.py](/Volumes/ORICO/code1/scripts/streamlit/report_studio.py): 自动化报告入口
- [deepinsight.dataops.macro_import](/Volumes/ORICO/code1/deepinsight/dataops/macro_import.py): 宏观 Excel 导入模块

## 当前数据状态

当前仓库已接入：

- 企业文档、财务事实、图谱扩展表
- Chroma 年报向量库
- 国家统计局卫生类宏观数据
