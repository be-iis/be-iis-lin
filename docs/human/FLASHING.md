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
