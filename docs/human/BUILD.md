# Build

Supported build hosts:

- Ubuntu/Debian x86-64
- Debian/Raspberry Pi OS arm64

## Prepare

```sh
bash scripts/prepare.sh
```

The script installs the native packages needed for both supported host
architectures. The firmware itself is cross-compiled with
`arm-none-eabi-gcc`.

## Host software

```sh
make host
make test
```

The editable virtual environment is stored in `.venv/`.

## STM32 firmware

```sh
make firmware-all
```

MicroPython is fetched into `build/micropython` and pinned to v1.27.0. The
BE-IIS patch script applies the STM32G0B0 and mboot adaptations.

Output:

```text
build/micropython/ports/stm32/build-BEIIS_LIN_HAT/firmware.bin
build/micropython/ports/stm32/build-BEIIS_LIN_HAT/firmware.elf
build/micropython/ports/stm32/mboot/build-BEIIS_LIN_HAT/firmware.elf
```

Flash layout:

| Range | Purpose |
|---|---|
| 0x08000000-0x08007fff | mboot, 32 KiB |
| 0x08008000-0x08057fff | MicroPython application, 320 KiB |
| 0x08058000-0x0807ffff | filesystem, 160 KiB |
