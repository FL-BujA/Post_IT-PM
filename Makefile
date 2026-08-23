.PHONY: gate sigsheet test

gate: sigsheet test

sigsheet:
	python3 tools/sigsheet.py --selftest
	python3 tools/sigsheet.py --check

test:
	python3 -m pytest -q
