# Flashing

There are two supported programming paths.

## Initial / factory programming: OpenOCD + ST-Link + SWD

Connect ST-Link to SWDIO, SWCLK and GND, then run:

```sh
make flash-swd
```

This builds and programs both mboot and the application. OpenOCD uses
`target/stm32g0x.cfg` and verifies both ELF images.

The bootloader intentionally is not hardware write-protected.

## Field update: Raspberry Pi I2C

Once mboot has been programmed once, application firmware can be updated through
the normal HAT I2C connection:

```sh
make flash-i2c
```

Defaults:

```text
I2C bus:     1
I2C address: 0x42
```

Override them if needed:

```sh
make flash-i2c I2C_BUS=1 I2C_ADDRESS=0x42
```

The CLI enters mboot, identifies the board, erases the required application
pages, writes the image, verifies SHA-256, marks the image valid and resets.

With application transport protocol v3, mboot entry is a native I2C control
operation. A running/autostart MicroPython runtime does not need to yield Raw
REPL before a field update. The mboot reset path is followed by a defined
application-side reset so the persistent runtime autostarts through the same
clean boot path used by normal recovery.

Direct invocation:

```sh
. .venv/bin/activate
beiis-lin --bus 1 --address 0x42 flash \
  build/micropython/ports/stm32/build-BEIIS_LIN_HAT/firmware.bin
```


## Daemon ownership during field updates

Only one process should own the HAT I2C endpoint.

If `beiis-lind` is stopped, a direct field update is appropriate:

```sh
beiis-lin --direct flash \
  build/micropython/ports/stm32/build-BEIIS_LIN_HAT/firmware.bin
```

If `beiis-lind` is already running, use the normal socket path instead of
opening I2C in parallel:

```sh
beiis-lin flash \
  build/micropython/ports/stm32/build-BEIIS_LIN_HAT/firmware.bin
```

The daemon-side `flash` operation receives a filesystem path on the same Linux
host.

## Runtime filesystem retention

The mboot application update programs the application region only. The
MicroPython filesystem is outside that region, so installed runtime applications
and `/flash/beiis/instances.json` are retained by a normal application update.

Re-run `scripts/install-standard-runtime.py` when the installed applications
or standard instance configuration changed, not merely because application
firmware was updated.

For the complete runtime workflow, see `RUNTIME_GUIDE.md`.
