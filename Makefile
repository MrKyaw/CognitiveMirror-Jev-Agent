.PHONY: venv test e2e perf postgres-test eval report report-full schemas serve mcp mcp-http demo lint \
	up down logs docker-build compose-smoke container-test

export PYTHONPATH := $(CURDIR)/src$(if $(PYTHONPATH),:$(PYTHONPATH))
PY ?= $(if $(wildcard .venv/bin/python),.venv/bin/python,python3)
PORT ?= 8000

venv:
	uv venv --python 3.12 .venv && uv pip install --python .venv/bin/python -r requirements-dev.txt

test:
	$(PY) -m pytest -q --cov --cov-report=term-missing --cov-fail-under=100

e2e:
	$(PY) -m pytest -q -m e2e

perf:
	$(PY) -m pytest -q -m perf

postgres-test:
	$(PY) -m pytest -q -m postgres

eval:
	$(PY) -m pytest -q -m eval -s

report:
	$(PY) tools/test_report.py

report-full:
	$(PY) tools/test_report.py --perf --container

schemas:
	$(PY) -m cognitive_mirror.schemas --write

serve:
	$(PY) -m cognitive_mirror.api --port $(PORT)

mcp:
	$(PY) -m cognitive_mirror.mcp_server --transport stdio

mcp-http:
	$(PY) -m cognitive_mirror.mcp_server --transport streamable-http --port $(PORT)

demo:
	$(PY) -m cognitive_mirror.examples.personal_agent
	$(PY) -m cognitive_mirror.examples.enterprise_agent

lint:
	$(PY) -m ruff check src tests tools

docker-build:
	docker build -t cognitive-mirror-jev-mcp:local .

up:
	docker compose up -d --build --wait

down:
	docker compose down -v

logs:
	docker compose logs -f

compose-smoke:
	bash tools/compose_smoke.sh

container-test: compose-smoke
