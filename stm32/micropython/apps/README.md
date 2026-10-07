# MicroPython runtime applications

This directory is the repository location for MicroPython applications that run
inside the persistent BE-IIS LIN HAT runtime.

These applications are product/runtime code. They are deliberately not stored
under `examples/`.

The firmware runtime itself remains in:

- `stm32/boards/BEIIS_LIN_HAT/frozen/beiis_boot.py`
- `stm32/boards/BEIIS_LIN_HAT/frozen/beiis_runtime.py`

Installed application modules live on the STM32 filesystem at:

```text
/flash/beiis/apps/<app>.py
```

and the persistent instance configuration is:

```text
/flash/beiis/instances.json
```

## Agreed runtime roles

The runtime has 16 available slots. The standard topology uses nine instances:

| Slot | Instance | Responsibility |
|---:|---|---|
| 0 | `master_tx_query` | application/host -> master query path |
| 1 | `master_rx_query` | master -> application/host query path |
| 2 | `master_native` | owns and controls master-side LIN operations |
| 3 | `slave_tx_query` | application/host -> slave query path |
| 4 | `slave_rx_query` | slave -> application/host query path |
| 5 | `slave_native` | owns and controls slave-side LIN operations |
| 6 | `logging_tx_query` | application/host -> logging control/query path |
| 7 | `logging_rx_query` | logging -> application/host data path |
| 8 | `logging_native` | logging/monitor controller |
| 9..15 | free | reserved for future runtime functions |

The central dispatcher remains part of `beiis_runtime.py`; it is not a tenth
instance.

## Source-of-truth rule

Do not recreate deployed runtime applications from memory.

Use `scripts/export-micropython-runtime.py` to copy the actual installed
application sources and `instances.json` from a HAT into this directory before
changing them. This avoids silently replacing working field code with a guessed
implementation.

## IP separation

There is no IP-over-LIN code in this directory, in the frozen MicroPython
runtime, or in the native STM32 application transport. The IP experiment lives
only in `examples/ip-over-lin/`.
