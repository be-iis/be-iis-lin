# STM32 / MicroPython integration

The generic stack is complete down to two hardware boundaries. These must be bound to the actual STM32 and schematic.

## LIN UART hooks

Implement for the UART connected to the LIN transceiver:

```c
int lin_port_set_baudrate(uint32_t baudrate);
int lin_port_send_break(void);
int lin_port_tx(const uint8_t *data,size_t len,uint32_t timeout_ms);
int lin_port_rx(uint8_t *data,size_t len,uint32_t timeout_ms);
```

Break generation, UART transfer and response timing stay in C.

## I2C target backend

Configure the STM32 as I2C target, normally 0x42. Interpret the first received byte as the register defined in `protocol/README.md`.

- write RX_DATA: `beiis_repl_host_write(payload,len)`
- read STATUS/RX_FREE/TX_COUNT/VERSION: `beiis_repl_reg_read_u8(reg)`
- read TX_DATA: `beiis_repl_host_read(buf,len)`
- write CONTROL: `beiis_repl_control(value)`

The I2C interrupt wakes the `__WFI()` used by the MicroPython stdin/stdout bridge.

## No MicroPython fork

Current STM32 MicroPython declares `mp_hal_stdin_rx_chr()` and `mp_hal_stdout_tx_strn()` weak. The BE-IIS user module supplies strong replacements, so upstream MicroPython can remain unchanged.

## Build

```sh
make micropython-build BOARD=<board>
```

For the final PCB:

```sh
make micropython-build BOARD=BEIIS_LIN_HAT BOARD_DIR=/path/to/BEIIS_LIN_HAT
```
