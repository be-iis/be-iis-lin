# Standalone MicroPython scripts

This directory contains direct MicroPython bring-up and hardware test scripts.

These scripts are not persistent runtime applications and are not registered as
runtime instances. Persistent application sources belong in
`stm32/micropython/apps/`.

Current scripts:

- `master.py` - repeated LIN1 master transmit test
- `request.py` - repeated LIN2 master request test
