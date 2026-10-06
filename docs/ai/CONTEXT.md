# AI context: BE-IIS LIN HAT

This directory is intentionally machine-oriented. It states current invariants,
interfaces and known limitations so an AI coding agent does not need to infer
them from scattered files.

## Product

- Repository: be-iis/be-iis-lin
- Hardware: BE-IIS dual-channel isolated LIN HAT for Raspberry Pi
- MCU: STM32G0B0KET6, Cortex-M0+, 512 KiB flash, 144 KiB RAM
- STM32 application: MicroPython 1.27.0 plus native C modules
- Linux host: Python 3 package with CLI + daemon
- default I2C address: 0x42
- production daemon socket: /run/beiis/lin-hat.sock
- tested Raspberry Pi IRQ input: GPIO6
- STM32 IRQ source pin: PC6

## Architecture invariant

Applications should use the Unix socket through beiis-lind. beiis-lind owns the
I2C endpoint. Direct I2C exists for development/recovery. The STM32 never sees
the Unix socket.

Keep time-critical LIN operations in C. MicroPython is a scripting layer, not
the timing engine.

## Flash

- mboot: 0x08000000, 32 KiB
- app:   0x08008000, 320 KiB
- fs:    0x08058000, 160 KiB
- initial programming: OpenOCD/ST-Link/SWD
- field update: Pi I2C/mboot
- bootloader is intentionally not WRP protected
