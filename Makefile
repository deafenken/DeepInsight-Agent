PYTHON ?= python3
STREAMLIT ?= streamlit
UVICORN ?= uvicorn

.PHONY: run run-basic run-advanced run-persona run-whitebox run-workflow web cache test

run:
	$(STREAMLIT) run scripts/streamlit/system_console.py --server.port 8501

run-basic:
	$(STREAMLIT) run scripts/streamlit/chat_console.py --server.port 8501

run-advanced:
	$(STREAMLIT) run scripts/streamlit/analysis_studio.py --server.port 8501

run-persona:
	$(STREAMLIT) run scripts/streamlit/stakeholder_console.py --server.port 8501

run-whitebox:
	$(STREAMLIT) run scripts/streamlit/trace_console.py --server.port 8501

run-workflow:
	$(STREAMLIT) run scripts/streamlit/report_studio.py --server.port 8501

web:
	$(UVICORN) webapp.main:app --host 0.0.0.0 --port 8000

cache:
	$(PYTHON) -m deepinsight.demo.demo_cache

test:
	$(PYTHON) -m unittest discover -s tests -v
