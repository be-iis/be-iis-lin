# AI context: protocols

## Linux socket protocol

Transport: AF_UNIX + SOCK_SEQPACKET.

JSON packet forms:

```json
{"v":1,"id":1,"type":"request","op":"ping","args":{}}
{"v":1,"id":1,"type":"reply","ok":true,"result":{}}
{"v":1,"id":1,"type":"event","event":"progress","data":{}}
```

Implementation:
- host/beiis_lin/socket_protocol.py
- host/beiis_lin/client.py
- host/beiis_lin/daemon.py

The daemon currently implements request/reply and firmware progress events.
Hardware IRQ-driven asynchronous LIN events are future work.

## Application I2C transport

Registers are documented in protocol/README.md. It is a byte-pipe carrying
MicroPython Raw REPL internally.

Important: CONTROL bit0 resets FIFOs. Do not assume a soft-reset bit exists
unless the C backend is changed accordingly.

## mboot

Implementation: host/beiis_lin/mboot.py plus the MicroPython patch.

STM32G0 validity invariant: the first application vector doubleword must stay
erased during the write and is programmed exactly once by the patched MARKVALID
operation. Do not revert to rewriting an already-programmed vector doubleword.
