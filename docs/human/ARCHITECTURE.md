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
Application-runtime management and framed data share the same physical I2C
endpoint through a separate native application transport. Raw REPL remains a
separate recovery/development byte pipe.

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
hardware. PC6 is now a level-based "host data available" notification. The
STM32 asserts it while application TX data or a completed native LIN slave-RX
frame is pending.

`beiis-lind` requests Raspberry Pi GPIO6 through the Linux GPIO character
device v2 API and listens to both edges. Application receive waits use GPIO6
instead of 1-ms I2C polling when the line is available. If GPIO access is not
available, the host transport falls back to the previous polling behaviour.


## Runtime and recovery path

The STM32 application transport supports up to sixteen stored MicroPython
instances and 32 user channels. Runtime management uses the reserved management
channel 0xff. Management replies and application frames are framed atomically on
the STM32-to-host path.

Application protocol v3 also exposes native recovery controls. The Linux host
can reset the STM32 or enter mboot without first gaining control of Raw REPL.
This is important because an autostart runtime intentionally owns the
MicroPython interpreter.

The STM32 I2C target transmit path defers software-FIFO consumption until the
host read transaction is complete. This avoids losing a byte when the STM32
prefetches TXDR before the master's final NACK.

## LIN indication

Each channel has active-low RX, TX, slave and master LEDs. Slave indication
remains active while a slave response is configured; master indication is active
during a master transaction. RX/TX indicate bus activity.

## Remote host testing

The normal transport is intentionally local. A remote test host can reach the
same Unix socket through SSH stream-local forwarding. No separate LAN protocol
is required for this test, so remote testing exercises the production daemon
protocol without adding an unauthenticated network service.


## Further reading

- `RUNTIME_GUIDE.md` - application/runtime usage and native LIN operations
- `SOCKET_API.md` - Unix socket protocol for C/Python/other host applications
