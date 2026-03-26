# 自动化研报工作流行为偏差

严重级别：中

## 问题

`workflow_report.py` 的页面标题和步骤文案都在强调“查询关系数据库”和“查询 ChromaDB 获取研报信息”，但实际执行的 `query_financial_sql()` 与 `query_chroma_chunks()` 完全返回固定 mock 数据，没有访问数据库，也没有访问向量库。

## 代码位置

- [workflow_report.py](/Volumes/ORICO/code1/workflow_report.py#L12)
- [workflow_report.py](/Volumes/ORICO/code1/workflow_report.py#L54)
- [workflow_report.py](/Volumes/ORICO/code1/workflow_report.py#L64)
- [workflow_report.py](/Volumes/ORICO/code1/workflow_report.py#L107)
- [workflow_report.py](/Volumes/ORICO/code1/workflow_report.py#L110)

## 具体表现

- SQL 文本指向 `mock_financial_result`，但这个对象不是数据库表
- 返回值始终是固定的 `MOCK_SQL_RESULT`
- 向量检索始终返回固定的 `MOCK_RAG_CHUNKS`
- 页面上还会把这些结果展示成“步骤二/步骤三”的真实执行产物

## 影响

- 用户会误以为系统已经打通真实数据源
- 生成的研报可能与输入主题不一致，只是套用了固定样本
- 后续验收时容易出现“演示可用、落地不可用”的偏差

## 建议

- 如果这是演示页，界面上明确标注“Mock Demo”
- 如果目标是真实工作流，直接复用 [retriever.py](/Volumes/ORICO/code1/retriever.py) 与 SQLite/Chroma 的现有能力，不要在页面层保留固定样本数据
