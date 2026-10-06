# BE-IIS LIN HAT software

Software stack for a BE-IIS LIN HAT with an STM32 connected to the Raspberry Pi through I2C.

## Architecture

```
Raspberry Pi
  beiis-lin host package
        |
        | I2C byte-pipe
        v
STM32 / MicroPython raw REPL
        |
        | built-in module: lin
        v
LIN C core -> board UART/break hooks -> LIN transceiver
```

The I2C link is deliberately only a transport. Python upload/execution uses MicroPython Raw REPL semantics instead of defining another scripting protocol.

## Tree

- `host/` Raspberry Pi Python API and CLI
- `protocol/` I2C byte-pipe specification
- `stm32/lib/lin/` portable LIN protocol core
- `stm32/lib/repl_i2c/` I2C REPL FIFOs
- `stm32/micropython/` MicroPython modules and integration
- `examples/` Python scripts intended to run on the STM32

## Host quick start

```sh
make host
. .venv/bin/activate
beiis-lin --bus 1 --address 0x42 ping
beiis-lin --bus 1 --address 0x42 run examples/master.py
```

## STM32 build

```sh
make micropython-fetch
make micropython-build BOARD=<micropython-stm32-board>
```

For the final PCB use a custom MicroPython STM32 board definition and implement the small hardware hooks documented in `stm32/micropython/README.md`.

The software above those hooks is independent of the exact STM32. Pinmux, clock tree, selected UART and I2C target peripheral are necessarily board-specific.
