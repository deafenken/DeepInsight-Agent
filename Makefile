PYTHON ?= python3
STREAMLIT ?= streamlit
UVICORN ?= uvicorn

.PHONY: run run-basic run-advanced run-persona run-whitebox run-workflow web cache test

run:
	$(STREAMLIT) run app_system.py --server.port 8501

run-basic:
	$(STREAMLIT) run app.py --server.port 8501

run-advanced:
	$(STREAMLIT) run app_advanced.py --server.port 8501

run-persona:
	$(STREAMLIT) run app_persona.py --server.port 8501

run-whitebox:
	$(STREAMLIT) run app_whitebox.py --server.port 8501

run-workflow:
	$(STREAMLIT) run workflow_report.py --server.port 8501

web:
	$(UVICORN) webapp.main:app --host 0.0.0.0 --port 8000

cache:
	$(PYTHON) demo_cache.py

test:
	$(PYTHON) -m unittest discover -s tests -v
