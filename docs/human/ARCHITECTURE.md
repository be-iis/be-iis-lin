# Architecture

## Design principle

The board is intentionally split into a real-time controller and a thin Linux
host layer.

- STM32 owns LIN timing.
- Native C owns time-critical LIN and I2C operations.
- MicroPython is the open scripting layer on the STM32.
- `beiis-lind` is the only normal Linux process that owns the HAT I2C endpoint.
- applications communicate with `beiis-lind` through Unix `SOCK_SEQPACKET`.

This avoids depending on Linux scheduling for LIN timing while keeping the host
API open and easy to automate.

## Data path

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

## Hardware mapping

| Function | STM32 pin |
|---|---|
| LIN1 TX | PB6 / USART1_TX |
| LIN1 RX | PB7 / USART1_RX |
| LIN1 enable | PA4 |
| LIN2 TX | PA2 / USART2_TX |
| LIN2 RX | PA3 / USART2_RX |
| LIN2 enable | PA8 |
| I2C SCL | PB8 / I2C1_SCL |
| I2C SDA | PB9 / I2C1_SDA |
| IRQ | PC6 |
| SWDIO | PA13 |
| SWCLK | PA14 |

The isolated IRQ path from STM32 PC6 to Raspberry Pi GPIO6 has been verified on
hardware. The current daemon does not yet use that IRQ for asynchronous events.
