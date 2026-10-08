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
- persistent multi-instance application runtime (up to 16 instances, 32 data channels)
- native runtime recovery: STM32 reset and direct mboot entry over I2C
- field update through mboot while the MicroPython runtime is active
- active-low master/slave/TX/RX LEDs for both LIN channels
- bidirectional LIN1/LIN2 master/slave operation verified with classic and enhanced checksums
- Unix SOCK_SEQPACKET daemon path verified end-to-end on hardware
- runtime management, application data, LIN and mboot/recovery verified through beiis-lind
- tested IRQ-driven host path: STM32 PC6 -> isolated IRQ -> Raspberry Pi GPIO6 -> beiis-lind
- beiis-lind currently exposes a local Unix socket only; no direct TCP listener

## Repository layout

- `host/` - Linux daemon, CLI, socket client, I2C transport and tests
- `stm32/` - board definition, native LIN core, I2C transport and MicroPython integration
- `protocol/` - STM32 I2C transport documentation
- `examples/` - isolated usage examples and experiments
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

Run the Linux socket daemon manually when needed:

```sh
.venv/bin/beiis-lind
```

## Documentation

Start here:

- `docs/human/RUNTIME_GUIDE.md` - native LIN control, master/slave paths,
  queries, custom workers, logging, flashing, C and Python integration
- `docs/human/SOCKET_API.md` - exact Unix `SOCK_SEQPACKET` JSON API
- `docs/human/HOST.md` - daemon, CLI, ownership and GPIO IRQ
- `docs/human/FLASHING.md` - SWD and I2C/mboot firmware updates
- `protocol/APP-RUNTIME.md` - STM32 runtime transport and instance model
- `examples/runtime/` - executable Python, C and custom-query examples
- `examples/ip-over-lin/` - isolated IP-over-LIN experiment

For remote testing over a LAN, see `docs/human/LAN_TEST.md`; the documented
test uses SSH Unix-socket forwarding and does not expose the daemon directly on
TCP.

## License and attribution

BSD-3-Clause. You may use, modify and redistribute the software, including in
commercial products. Redistributions must retain the copyright and license
notices as described in `LICENSE`.

Original project: **BE-IIS / Brechel Electronic - Industrial Interface Systems**  
https://www.be-iis.eu/


## MicroPython application runtime

The STM32 can store and autostart up to sixteen MicroPython application
instances. One instance slot is selected as the active owner of the normal
Pi data interface; optional tap instances receive copies without consuming
the owner's data. The existing Raw-REPL path remains available separately.

See `protocol/APP-RUNTIME.md`.
