# BE-IIS LIN HAT

Open software stack for the **BE-IIS dual-channel isolated LIN HAT for Raspberry Pi**.

The HAT uses an STM32G0B0 as a real-time LIN controller. Linux applications talk
to `beiis-lind` through a local Unix `SOCK_SEQPACKET` socket; the daemon owns
the I2C connection to the STM32. The STM32 runs MicroPython for the scripting
layer while time-critical LIN and I2C functions stay in native C.

## Architecture

```text
Linux application / beiis-lin
          |
          | Unix SOCK_SEQPACKET
          v
      beiis-lind
          |
          | I2C, default address 0x42
          v
 STM32G0B0 + MicroPython
          |
          | native C LIN engine
          v
     LIN1 / LIN2
```

The Unix socket exists only on Linux. The STM32 sees I2C, not the socket.

## Current status

- two independent LIN channels
- master transmit
- master request
- classic and enhanced checksum
- slave response
- MicroPython scripting
- I2C Raw-REPL transport
- I2C mboot firmware update with hash verification
- OpenOCD/ST-Link initial programming
- Linux `beiis-lind` daemon with `SOCK_SEQPACKET`
- host CLI and Python client
- persistent multi-instance application runtime (up to 8 instances, 32 data channels)
- tested IRQ hardware path: STM32 PC6 -> isolated IRQ -> Raspberry Pi GPIO6
- IRQ-driven daemon events are not integrated yet

## Repository layout

- `host/` - Linux daemon, CLI, socket client, I2C transport and tests
- `stm32/` - board definition, native LIN core, I2C transport and MicroPython integration
- `protocol/` - STM32 I2C transport documentation
- `examples/` - scripts intended to run on the STM32
- `scripts/` - preparation, build, test, flashing and installation helpers
- `docs/human/` - documentation for users and developers
- `docs/ai/` - concise machine-oriented project context and invariants

## Quick start

On Ubuntu x86-64 or Raspberry Pi OS / Debian arm64:

```sh
bash scripts/prepare.sh
make host
make test
```

Build both bootloader and application firmware:

```sh
make firmware-all
```

Initial programming with ST-Link/SWD:

```sh
make flash-swd
```

Field update through the Raspberry Pi I2C connection:

```sh
make flash-i2c
```

Install the Linux daemon:

```sh
sudo bash scripts/install-daemon.sh
```

See `docs/human/` for build, flashing, host and LIN API details.

## License and attribution

BSD-3-Clause. You may use, modify and redistribute the software, including in
commercial products. Redistributions must retain the copyright and license
notices as described in `LICENSE`.

Original project: **BE-IIS / Brechel Electronic - Industrial Interface Systems**  
https://www.be-iis.eu/


## MicroPython application runtime

The STM32 can store and autostart up to eight MicroPython application
instances. One instance slot is selected as the active owner of the normal
Pi data interface; optional tap instances receive copies without consuming
the owner's data. The existing Raw-REPL path remains available separately.

See `protocol/APP-RUNTIME.md`.
