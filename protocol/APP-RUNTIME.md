# BE-IIS LIN HAT application runtime

This runtime is additive to the existing I2C Raw-REPL transport. The existing
Raw REPL registers and behaviour are intentionally unchanged.

## Limits

- Up to 16 configured application instances, with stable slots 0 through 15.
- Exactly one slot is the active owner of the normal Pi data interface; reset default is slot 0.
- Optional tap instances receive copies without consuming the active owner's data.
- 32 user data channels: 0 through 31.
- One internal management channel: 0xff.
- Maximum application frame payload: 2048 bytes.
- Maximum installed Python application file: 64 KiB.
- Per-instance mailbox depth: 16 messages.

The 16 application instances share one MicroPython interpreter. They are
cooperatively scheduled using `asyncio`; they are not isolated processes.

## Additional I2C registers

The device remains at the normal application address `0x42`.

| Register | Name | Direction | Meaning |
|---|---|---|---|
| 0x03 | APP_RX_FREE | R | free bytes in Pi -> STM application FIFO, saturated at 255 |
| 0x04 | APP_TX_COUNT | R | bytes waiting in STM -> Pi application FIFO, saturated at 255 |
| 0x05 | APP_STATUS | R | bit0 writable, bit1 readable, bit7 alive |
| 0x11 | APP_RX_DATA | W | append framed application bytes |
| 0x21 | APP_TX_DATA | R | pop framed application bytes |
| 0x32 | APP_VERSION | R | application transport version |
| 0x33 | APP_CHANNELS | R | number of user channels, currently 32 |
| 0x34 | APP_CONTROL | W | bit0 resets only application FIFOs; bit6 enters mboot; bit7 resets the STM32. Reset/bootloader actions occur after the I2C transaction completes |
| 0x35 | APP_MAX_PAYLOAD_LO | R | payload limit, low byte |
| 0x36 | APP_MAX_PAYLOAD_HI | R | payload limit, high byte |
| 0x37 | APP_ACTIVE_INSTANCE | R/W | active application slot 0..15, reset default 0 |

Raw REPL continues to use its original register set. The bit6 mboot entry and bit7 reset are implemented natively and remain available even if the MicroPython runtime or Raw REPL is not responsive.

## Application frame

The two FIFO directions have intentionally simple, direction-specific headers.

Pi -> STM:

```text
byte 0      channel
byte 1..2   payload length, little endian
byte 3..    payload
```

The native `APP_ACTIVE_INSTANCE` register selects which instance owns this
traffic.

STM -> Pi:

```text
byte 0      source instance (0..15)
byte 1      channel
byte 2..3   payload length, little endian
byte 4..    payload
```

Management replies use source instance `0xff` and channel `0xff`. This source
tag lets an active application and one or more TAP/logger instances send data to
the Pi in parallel without ambiguity.

Channels `0..31` carry user data. Channel `0xff` is reserved for runtime
management and is not counted among the 32 user channels.

Normal user-data frames are delivered only to the running instance whose stable
slot matches `APP_ACTIVE_INSTANCE`. The register resets to slot 0 and is native,
so the Pi can read or change it without using the MicroPython REPL. Instances
configured as taps receive a copy after the active owner has been selected; they
never steal the owner's frame. A tap with an empty channel list sees all user
channels, otherwise its channel list acts as a tap filter.

Any running instance may send user data back to the Pi. The STM -> Pi frame
contains the source slot, so a logger or monitor can report independently while
the selected active instance continues to own Pi -> STM data.

A host may split a frame across multiple I2C writes to `APP_RX_DATA`. The STM
does not expose a partial STM->host packet: the native transport commits a
complete frame atomically.

## Stored applications and instances

Application modules are stored in:

```text
/flash/beiis/apps/<app>.py
```

Persistent instance configuration is stored in:

```text
/flash/beiis/instances.json
```

An instance selects an application module, a stable slot, an instance name,
optional tap channels, optional configuration, optional resource claims, a tap
flag, and an autostart flag. Multiple instances may use the same application
module. Slots are allocated from 0 through 15 and remain stable in the stored
configuration.

The frozen boot hook starts the runtime only when at least one configured
instance has `autostart=true`. If no instance is configured for autostart,
normal `boot.py` and Raw REPL behaviour remains available.

## Application contract

An installed module provides `main(ctx)`. For multiple instances it should be
an async function, or otherwise return regularly to the scheduler.

```python
async def main(ctx):
    while True:
        source, channel, payload = await ctx.recv()

        # Send data to the Pi on one of the 32 user channels.
        await ctx.send_host(channel, payload)

        # Direct instance-to-instance message.
        ctx.send_to("other_instance", b"hello", channel=7)

        # Broadcast locally to all other instances subscribed to channel 5.
        ctx.publish(5, b"event")
```

`ctx.recv()` returns `(source, channel, payload)`. `source` is either
`"host"` or the name of another instance. `ctx.slot` is the stable slot
number and is carried as the source-instance byte when that app sends to the Pi.

## Resource ownership

Instances may claim named hardware resources such as `lin1` or `lin2`.
The runtime refuses to start a second instance that claims a resource already
owned by a running instance. Claims are released when the instance stops or
crashes.

This is intentionally simple: it prevents two Python applications from
reconfiguring the same hardware peripheral behind each other's back.

## Lifecycle and failures

Instances have the states `starting`, `running`, `stopped`, or `crashed`.
An exception in one cooperative task is recorded for that instance instead of
being treated as an intentional reboot of the whole runtime.

Application mailbox overflow is bounded and counted. The runtime does not
persist application log data.

A non-yielding Python loop can still block all other Python instances because
there is only one MicroPython interpreter. Native interrupt-driven LIN and I2C
code remain separate from that cooperative Python scheduling.

## Management channel

Channel `0xff` carries JSON request/reply packets with a numeric request ID.
Implemented operations include:

`info`, `app_list`, `install_begin`, `install_chunk`, `install_commit`,
`app_remove`, `instance_add`, `instance_remove`, `instance_configure`,
`instance_list`, `active_instance`, `start`, `stop`, `restart`, `autostart`, and
`runtime_stop`.

App installation is chunked and verified with file size plus CRC32 before the
new module is activated.

`runtime_stop` stops all instances and returns control to normal MicroPython
boot/REPL flow without changing the stored configuration.


## Host notification IRQ

The STM32 board provides an isolated host-notification signal on PC6, connected
to Raspberry Pi GPIO6.

For the application transport, PC6 is asserted while the STM32 -> host
application FIFO is non-empty and deasserted after the host consumes the pending
data. The board combines this with other host-visible readiness sources, so one
source cannot clear an interrupt while another source remains pending.

`beiis-lind` uses GPIO6 events to sleep between I2C reads instead of polling
`APP_TX_COUNT` every millisecond. The I2C status/count register remains the
source of truth after wakeup, so missed/spurious GPIO edges do not change the
framing protocol.

If GPIO event access is unavailable, the host may fall back to polling without
changing the I2C protocol.
