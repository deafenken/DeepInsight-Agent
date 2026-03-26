# 运行阻塞问题

## 1. `ZhipuEmbeddingClient` 实例化即报 `NameError`

严重级别：高

### 问题

`data_pipeline.py` 中定义了 `ZhipuEmbeddingClient`，但文件顶部没有导入 `os`。该类在 `__init__` 中直接调用 `os.getenv(...)`，因此只要实例化就会失败。

### 代码位置

- [data_pipeline.py](/Volumes/ORICO/code1/data_pipeline.py#L52)

### 现场验证

执行：

```bash
python3 - <<'PY'
from data_pipeline import ZhipuEmbeddingClient
ZhipuEmbeddingClient(api_key='x')
PY
```

结果：

```text
NameError: name 'os' is not defined
```

### 影响

- 如果后续准备切换到智谱 embedding，这条链路会立即中断
- 这个问题不会被 `py_compile` 捕获，属于运行时故障

### 建议

- 在文件顶部补充 `import os`
- 增加一个最小化单测或 smoke test，至少覆盖实例化过程

## 2. 检索链路在当前环境不可运行，且仓库缺少依赖清单

严重级别：高

### 问题

仓库里没有 `requirements.txt`、`pyproject.toml`、`Pipfile` 或 `environment.yml`，当前环境中也缺少 `chromadb`。`retriever.py` 的检索逻辑依赖它，因此本地无法直接复现问答链路。

### 代码位置

- [retriever.py](/Volumes/ORICO/code1/retriever.py#L266)

### 现场验证

执行：

```bash
python3 - <<'PY'
from retriever import answer_query
answer_query('请分析ST生物的风险', filters={}, top_k=3, client=None)
PY
```

结果：

```text
RuntimeError: 未安装 chromadb。
```

同时检查到：

```text
requirements.txt False
pyproject.toml False
Pipfile False
environment.yml False
```

### 影响

- 新环境无法可靠安装依赖
- 即使数据库文件存在，RAG 功能也不能直接启动

### 建议

- 补充依赖清单
- 写明最小运行步骤，至少包含 `streamlit`、`chromadb`、`requests`、`openai`、`faker`、`streamlit-echarts`、`pdfplumber`、`langchain-text-splitters`

## 3. 主问答页面没有无密钥降级路径

严重级别：中

### 问题

`app.py` 在执行问答时总是调用 `get_client()`，而 `get_client()` 最终会构造 `DeepSeekClient`。如果环境里没有 `DEEPSEEK_API_KEY`，页面会在首次提问时失败，而不是退回到本地检索摘要模式。

### 代码位置

- [app.py](/Volumes/ORICO/code1/app.py#L107)
- [retriever.py](/Volumes/ORICO/code1/retriever.py#L45)

### 现场验证

当前环境变量状态：

```text
DEEPSEEK_API_KEY False
ZHIPU_API_KEY False
```

### 影响

- 当前环境下主页面无法完成正常问答
- 项目虽然实现了 `client=None` 的文本回退逻辑，但 UI 层没有使用它

### 建议

- 在 `get_client()` 中改为“可选创建”
- 若缺少 API Key，则调用 `answer_query(..., client=None)`，至少保留本地 SQL/RAG 摘要能力
