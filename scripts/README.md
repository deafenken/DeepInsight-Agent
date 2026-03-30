# 启动脚本目录

这个目录只保留面向演示和本地运行的启动脚本，避免项目根目录堆满薄封装文件。

## Streamlit 页面入口

- `streamlit run scripts/streamlit/system_console.py`
- `streamlit run scripts/streamlit/chat_console.py`
- `streamlit run scripts/streamlit/analysis_studio.py`
- `streamlit run scripts/streamlit/stakeholder_console.py`
- `streamlit run scripts/streamlit/trace_console.py`
- `streamlit run scripts/streamlit/report_studio.py`

## 数据与缓存脚本

这类脚本统一改为模块方式运行：

- `python3 -m deepinsight.dataops.db_init`
- `python3 -m deepinsight.dataops.db_expand`
- `python3 -m deepinsight.dataops.data_pipeline`
- `python3 -m deepinsight.dataops.macro_import`
- `python3 -m deepinsight.dataops.graph_data_pipeline`
- `python3 -m deepinsight.demo.demo_cache`
