# 项目检查报告

检查时间：2026-03-24

本次检查以“当前目录项目能否正常运行、是否存在明显行为偏差”为重点，做了以下验证：

- 阅读核心入口与数据链路：`app.py`、`app_advanced.py`、`retriever.py`、`data_pipeline.py`、`agent_tools.py`、`workflow_report.py`
- 运行语法编译检查：`python3 -m py_compile ...`
- 检查本地数据库表结构：`sqlite3 data/enterprise_analysis.db '.tables'`
- 运行少量函数级验证，确认当前环境中的真实失败点

## 结论

当前项目没有明显的 Python 语法错误，但存在数个会影响实际使用的问题：

1. `data_pipeline.py` 中的 `ZhipuEmbeddingClient` 一实例化就会因为缺少 `os` 导入而抛出 `NameError`
2. 当前环境缺少 `chromadb`，同时仓库也没有依赖清单，导致检索链路无法直接复现
3. 主问答页面依赖 `DEEPSEEK_API_KEY`，当前环境未配置，无法优雅降级到本地模式
4. `app_advanced.py` 通过导入 `app.py` 触发了第二次 `st.set_page_config(...)`，高概率导致 Streamlit 页面初始化异常
5. `workflow_report.py` 展示的是“自动化研报工作流”，但 SQL 与向量检索实际上完全使用 mock 数据

## 报告文件

- [01-runtime-blockers.md](/Volumes/ORICO/code1/audit_md/01-runtime-blockers.md)
- [02-streamlit-page-config.md](/Volumes/ORICO/code1/audit_md/02-streamlit-page-config.md)
- [03-workflow-behavior-mismatch.md](/Volumes/ORICO/code1/audit_md/03-workflow-behavior-mismatch.md)

## 补充说明

- 本次没有修改业务代码，只新增了 Markdown 审查报告
- 语法编译通过，不代表运行时依赖与页面生命周期没有问题
