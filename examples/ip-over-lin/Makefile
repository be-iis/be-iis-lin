ROOT := ../..
PYTHON := $(ROOT)/.venv/bin/python

.PHONY: unit hardware ping

unit:
	cd $(CURDIR) && $(PYTHON) -m unittest -v test_bridge.py

hardware:
	sudo bash $(CURDIR)/test-hardware.sh

ping:
	sudo RUN_IPERF=0 bash $(CURDIR)/test-hardware.sh
