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

Direct invocation:

```sh
. .venv/bin/activate
beiis-lin --bus 1 --address 0x42 flash \
  build/micropython/ports/stm32/build-BEIIS_LIN_HAT/firmware.bin
```

## Application update checklist

Use the normal I²C update only when the existing MicroPython Raw-REPL responds:

```sh
git switch main
git pull --ff-only
make host
make firmware-all
make test
./.venv/bin/beiis-lin --direct exec "import lin; print(lin.tic())"
make flash-i2c
```

The application uses `0x08008000` and the factory-installed mboot starts at
`0x08000000`. Routine I²C updates preserve mboot. If the application is
unresponsive over Raw-REPL, do not attempt to erase the bootloader blindly.
An application-only SWD recovery is possible using its addressed HEX file:

```sh
sudo openocd -f interface/stlink.cfg -f target/stm32g0x.cfg \\
  -c "transport select swd" -c "adapter speed 100" \\
  -c "reset_config srst_only srst_nogate connect_assert_srst" \\
  -c "init" -c "reset halt" \\
  -c "flash write_image erase build/micropython/ports/stm32/build-BEIIS_LIN_HAT/firmware.hex" \\
  -c "verify_image build/micropython/ports/stm32/build-BEIIS_LIN_HAT/firmware.hex" \\
  -c "reset run" -c "shutdown"
```

Verify the HEX image targets the application area before using SWD. A power
cycle may be necessary after halting under a debugger. Then check
`i2cdetect -y 1` and `./.venv/bin/beiis-lin --direct info`.
