ROOT := ../..
PYTHON ?= $(ROOT)/.venv/bin/python
CC ?= cc

.PHONY: check python-check c-check

check: python-check c-check

python-check:
	$(PYTHON) -m py_compile \
		python_basic.py \
		install_custom_query.py \
		custom_query_client.py \
		custom_query_worker.py

c-check:
	$(CC) -std=c11 -Wall -Wextra -fsyntax-only c_basic.c
