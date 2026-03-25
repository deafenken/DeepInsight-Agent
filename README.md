# 企业运营分析与决策支持系统

一个基于 Streamlit 的企业分析演示项目，包含基础问答、统一工作台、高级分析和自动化研报流程。

## 安装依赖

```bash
python -m pip install -r requirements.txt
```

## 初始化数据

```bash
python db_init.py
```

## 启动页面

基础问答页：

```bash
streamlit run app.py
```

统一系统页：

```bash
streamlit run app_system.py
```

可选页面：

```bash
streamlit run app_advanced.py
streamlit run workflow_report.py
```

## 环境变量

必需（启用 DeepSeek 能力时）：

```bash
export DEEPSEEK_API_KEY=your_key
```

可选：

```bash
export DEEPSEEK_MODEL=deepseek-chat
```

## 降级说明

- 未配置 `DEEPSEEK_API_KEY` 时，部分页面会进入本地降级模式。
- 未准备好 Chroma 数据或依赖时，向量检索相关能力会部分不可用。
- 自动化研报页在无 key 时会输出结构化本地结果，而不是完整 LLM 生成报告。
