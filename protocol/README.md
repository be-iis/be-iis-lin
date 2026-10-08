# BE-IIS STM32 I2C transport

Default I2C target address: `0x42`.

The application firmware exposes a byte-pipe used internally for MicroPython Raw
REPL traffic. Linux applications should normally use `beiis-lind`, not this
register interface directly.

| Register | Name | Direction | Meaning |
|---|---|---|---|
| 0x00 | STATUS | R | bit0 host->STM writable, bit1 STM->host readable, bit7 alive |
| 0x01 | RX_FREE | R | free bytes in host->STM FIFO, saturated at 255 |
| 0x02 | TX_COUNT | R | bytes waiting in STM->host FIFO, saturated at 255 |
| 0x10 | RX_DATA | W | append bytes to MicroPython stdin FIFO |
| 0x20 | TX_DATA | R | pop bytes from MicroPython stdout FIFO |
| 0x30 | CONTROL | W | bit0 reset FIFOs; other bits currently reserved |
| 0x31 | VERSION | R | application transport protocol version, currently 1 |

A write is `[register, payload...]`. A read selects a register with a one-byte
write, followed by a read transaction.

## mboot over I2C

The same I2C address is used by mboot. Application protocol v3 can enter mboot
through a native application-control operation, so field updates do not depend
on `machine.bootloader()` or Raw REPL availability. The host implementation is
in `host/beiis_lin/mboot.py`.

The updater:
1. identifies the board,
2. erases only the required application pages,
3. leaves the first application vector doubleword erased,
4. writes the remainder of the image,
5. verifies the invalid-image hash,
6. programs the original first 8 vector bytes once using MARKVALID,
7. verifies the final SHA-256,
8. resets into the application.

The one-shot first-vector flow is required by STM32G0 flash/ECC behaviour.


## Parallel application data transport

The Raw-REPL byte pipe remains unchanged. A second framed transport (currently
protocol v3) provides long-running MicroPython application instances, 32 user
channels, stored apps, autostart, active-instance selection, optional tap
instances, and native reset/mboot recovery controls.

See [APP-RUNTIME.md](APP-RUNTIME.md).
