PYTHON ?= python3

.PHONY: install test lint scan-demo

install:
	$(PYTHON) -m pip install -e .[dev]

test:
	pytest tests/ -v

lint:
	ruff check src/ tests/

scan-demo:
	$(PYTHON) -m demandradar.cli scan --sources hn,github,reddit --topic "developer tools" --output examples/sample_output.json
