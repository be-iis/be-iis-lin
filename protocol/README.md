# BE-IIS I2C Raw-REPL transport

Default I2C target address: `0x42`.

The transport exposes two byte FIFOs. It does not interpret Python; the stream is MicroPython REPL traffic.

| Register | Name | Direction | Meaning |
|---|---|---|---|
| 0x00 | STATUS | R | bit0 host->STM writable, bit1 STM->host readable, bit7 alive |
| 0x01 | RX_FREE | R | free bytes in host->STM FIFO, saturated at 255 |
| 0x02 | TX_COUNT | R | bytes waiting in STM->host FIFO, saturated at 255 |
| 0x10 | RX_DATA | W | append bytes to MicroPython stdin FIFO |
| 0x20 | TX_DATA | R | pop bytes from MicroPython stdout FIFO |
| 0x30 | CONTROL | W | bit0 reset FIFOs, bit1 soft-reset request |
| 0x31 | VERSION | R | protocol version, currently 1 |

A write is `[register, payload...]`.
A read selects a register with a one-byte write, then performs a repeated-start read.

Above this byte pipe the host enters standard MicroPython Raw REPL (Ctrl-A), sends source and terminates it with Ctrl-D. This intentionally keeps code execution compatible with MicroPython semantics.
