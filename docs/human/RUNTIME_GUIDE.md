# Runtime and LIN usage guide

This guide explains how to use the BE-IIS LIN HAT from Linux applications,
how the standard runtime is structured, how to control the native LIN engine,
how to use and extend query instances, and how firmware updates fit into the
stack.

For the exact Unix-socket JSON protocol, see `SOCKET_API.md`.

## 1. Mental model

There are three distinct layers:

```text
Linux application
      |
      | Unix SOCK_SEQPACKET
      v
  beiis-lind
      |
      | I2C application transport
      v
STM32 MicroPython runtime
      |
      | query instances
      v
native worker instance
      |
      | native C module
      v
     LIN bus
```

The STM32 owns LIN timing. Linux does not bit-bang LIN.

The normal production path is the persistent MicroPython runtime. Direct Raw
REPL access exists for development and recovery, but it is not the normal
application path.

## 2. Start the Linux daemon

Normal applications should connect to `beiis-lind`; they should not open I2C
independently.

Production/default socket:

```text
/run/beiis/lin-hat.sock
```

For development, a user-writable temporary socket is convenient:

```sh
. .venv/bin/activate

beiis-lind \
  --bus 1 \
  --address 0x42 \
  --socket /tmp/beiis-lin.sock \
  --lock-file /tmp/beiis-lind.lock
```

Check the connection from another shell:

```sh
beiis-lin --socket /tmp/beiis-lin.sock info
```

The daemon should report the device protocol and, on Raspberry Pi hardware,
GPIO6 IRQ information.

Only one process should own the HAT I2C endpoint. Do not run a direct-I2C client
while `beiis-lind` is using the same bus/address.

## 3. Standard nine-instance runtime

The standard installation uses nine of the sixteen available runtime slots:

| Slot | Instance | App | Purpose |
|---:|---|---|---|
| 0 | `master_tx_query` | `query` | host -> master worker |
| 1 | `master_rx_query` | `query` | master worker -> host |
| 2 | `master_native` | `lin_native` | owns LIN1 |
| 3 | `slave_tx_query` | `query` | host -> slave worker |
| 4 | `slave_rx_query` | `query` | slave worker -> host |
| 5 | `slave_native` | `lin_native` | owns LIN2 |
| 6 | `logging_tx_query` | `query` | host -> logging worker |
| 7 | `logging_rx_query` | `query` | logging worker -> host |
| 8 | `logging_native` | `logging_native` | logger control/status |
| 9..15 | free | - | custom applications |

Install the standard layout after flashing a compatible firmware:

```sh
python scripts/install-standard-runtime.py
```

The installer writes the reusable applications, recreates the deterministic
slot layout, enables autostart, selects slot 0 and resets the STM32.

### Important naming rule

`master_tx_query` and `master_rx_query` do **not** mean LIN-bus TX and RX.

They describe the direction through the runtime:

```text
host
  |
  v
master_tx_query
  |
  v
master_native
  |
  v
master_rx_query
  |
  v
host
```

The actual LIN operation is encoded in the binary request sent to
`master_native`.

The same rule applies to slave and logging query pairs.

## 4. Selecting a query path

Pi -> STM application traffic is delivered to exactly one active instance slot.
The active slot is selected natively and does not require Raw REPL.

Standard selections are:

| Function | Active TX slot | Expected reply slot |
|---|---:|---:|
| master | 0 | 1 |
| slave | 3 | 4 |
| logging | 6 | 7 |

Python:

```python
from beiis_lin.client import DaemonClient

c = DaemonClient()
c.set_active_instance(0)       # master_tx_query
c.data_send(0, b"\x00")      # generic native PING
instance, channel, reply = c.data_recv(instance=1, channel=0)
print(instance, channel, reply.hex())
c.close()
```

Expected native reply:

```text
00 00
^  ^
|  +-- status 0 = OK
+----- operation 0x00 = PING
```

Application channel 0 is used by the standard query layout. The runtime itself
supports user channels 0..31.

## 5. Generic native LIN RPC

Both `master_native` and `slave_native` run the same `lin_native.py`.
Only their configured physical LIN channel differs.

Request format:

```text
byte 0      operation
byte 1..    operation-specific payload
```

Reply format:

```text
byte 0      echoed operation
byte 1      status
byte 2..    result or short error text
```

Status:

| Value | Meaning |
|---:|---|
| 0 | OK |
| 1 | malformed request |
| 2 | native/LIN error |
| 3 | internal worker error |

Flag bit 0 selects checksum type:

| flags bit0 | Checksum |
|---:|---|
| 0 | classic |
| 1 | enhanced |

### Operations

| Op | Name | Request payload |
|---:|---|---|
| 0x00 | PING | none |
| 0x01 | INIT | baud:u32 little-endian |
| 0x02 | SEND | id, flags, len, data |
| 0x03 | REQUEST | id, flags, len |
| 0x04 | SLAVE_SET | id, flags, len, data |
| 0x05 | SLAVE_CLEAR | none |
| 0x06 | LEDS_GET | none |
| 0x07 | LEDS_SET | mask |
| 0x08 | SLAVE_RX_SET | id, flags, len |
| 0x09 | SLAVE_RX_RECV | none |

## 6. Master operation

The standard master worker owns LIN1.

### 6.1 Master transmit

A master-published LIN frame uses `SEND`:

```text
02 12 01 04 11 22 33 44
|  |  |  |  +----------- data
|  |  |  +-------------- length = 4
|  |  +----------------- enhanced checksum
|  +-------------------- LIN ID 0x12
+----------------------- SEND
```

Python:

```python
c.set_active_instance(0)
request = bytes((0x02, 0x12, 0x01, 4)) + bytes.fromhex("11 22 33 44")
c.data_send(0, request)
_, _, reply = c.data_recv(instance=1, channel=0, timeout=2.0)
assert reply == b"\x02\x00"
```

### 6.2 Master request / receive slave response

A master request sends a LIN header and receives the slave response:

```text
03 22 01 04
|  |  |  |
|  |  |  +-- requested data length
|  |  +----- enhanced checksum
|  +-------- LIN ID 0x22
+----------- REQUEST
```

Reply:

```text
03 00 04 11 22 33 44
|  |  |  +----------- received data
|  |  +-------------- received length
|  +----------------- OK
+-------------------- REQUEST
```

Python:

```python
c.set_active_instance(0)
c.data_send(0, bytes((0x03, 0x22, 0x01, 4)))
_, _, reply = c.data_recv(instance=1, channel=0, timeout=2.0)

if reply[:2] != b"\x03\x00":
    raise RuntimeError(reply)

length = reply[2]
data = reply[3:3 + length]
print(data.hex(" "))
```

## 7. Slave operation

The standard slave worker owns LIN2.

Select its TX query first:

```python
c.set_active_instance(3)
```

Replies are read from slot 4.

### 7.1 Configure a slave response

`SLAVE_SET` prepares data that will be transmitted when an external master
requests the configured identifier:

```python
payload = bytes((0x04, 0x22, 0x01, 4)) + bytes.fromhex("11 22 33 44")
c.data_send(0, payload)
_, _, reply = c.data_recv(instance=4, channel=0)
assert reply == b"\x04\x00"
```

Disable that response:

```python
c.data_send(0, b"\x05")
_, _, reply = c.data_recv(instance=4, channel=0)
assert reply == b"\x05\x00"
```

### 7.2 Receive a master-published frame as slave

Configure one receive identifier:

```python
# Receive 8 data bytes on LIN ID 0x12 with enhanced checksum.
c.data_send(0, bytes((0x08, 0x12, 0x01, 8)))
_, _, reply = c.data_recv(instance=4, channel=0)
assert reply == b"\x08\x00"
```

Fetch the received frame non-blocking:

```python
c.data_send(0, b"\x09")
_, _, reply = c.data_recv(instance=4, channel=0)

if reply[:2] != b"\x09\x00":
    raise RuntimeError(reply)

if reply[2] == 0:
    print("no frame ready")
else:
    length = reply[3]
    print(reply[4:4 + length].hex(" "))
```

Current implementation limitation: one slave receive identifier and one pending
receive buffer are configured per LIN channel. Applications that need a queue or
multiple receive identifiers should add that policy above the native primitive
or extend the native layer deliberately.

## 8. Change LIN baud rate

The standard instances start at 19200 baud.

The native worker can be reinitialized at runtime with `INIT`:

```python
baud = 9600
request = b"\x01" + baud.to_bytes(4, "little")
c.set_active_instance(0)
c.data_send(0, request)
_, _, reply = c.data_recv(instance=1, channel=0)
```

The current native LIN core accepts 1000..20000 bit/s.

For a persistent default, change the `baud` field in the instance
configuration and restart that instance.

## 9. Query instances

`query.py` is deliberately small and reusable.

A TX query:

- accepts only messages whose source is `"host"`,
- forwards payload and channel unchanged to its configured peer.

An RX query:

- accepts only messages from its configured native peer,
- forwards payload and channel unchanged to the host.

This separation keeps application protocols out of the common transport layer.

### Why use query pairs?

They provide a stable boundary:

```text
Linux protocol/application
        |
        v
      query
        |
        v
  hardware/service worker
        |
        v
      query
        |
        v
Linux protocol/application
```

The worker can be replaced without changing the Linux socket protocol.

## 10. Writing your own query-backed worker

You normally reuse `query.py` and write only the middle worker.

Minimal worker:

```python
BEIIS_API = 1

async def main(ctx):
    tx_peer = ctx.config["tx_peer"]
    rx_peer = ctx.config["rx_peer"]

    while True:
        source, channel, payload = await ctx.recv()
        if source != tx_peer:
            continue

        reply = b"reply:" + bytes(payload).upper()
        ctx.send_to(rx_peer, reply, channel)
```

The repository contains a complete working example under
`examples/runtime/`:

- `custom_query_worker.py`
- `install_custom_query.py`
- `custom_query_client.py`

The installer reuses the standard `query` app and creates:

```text
custom_tx_query -> custom_native -> custom_rx_query
```

in free runtime slots.

### Runtime application API

An installed application exports:

```python
BEIIS_API = 1

async def main(ctx):
    ...
```

Useful context methods:

```python
source, channel, payload = await ctx.recv()

await ctx.send_host(channel, payload)
ctx.send_to("other_instance", payload, channel)
ctx.publish(channel, payload)
```

Useful properties:

```text
ctx.name
ctx.app
ctx.config
ctx.channels
ctx.resources
ctx.slot
ctx.tap
ctx.api_version
```

Instances can claim resources such as `lin1` or `lin2`. The runtime prevents
two running instances from owning the same named resource.

## 11. Logging

The standard topology already contains:

```text
logging_tx_query -> logging_native -> logging_rx_query
```

Select slot 6 and receive from slot 7.

PING:

```python
c.set_active_instance(6)
c.data_send(0, b"\x00")
_, _, reply = c.data_recv(instance=7, channel=0)
print(reply.hex(" "))        # 00 00
```

STATUS:

```python
c.data_send(0, b"\x01")
_, _, reply = c.data_recv(instance=7, channel=0)
print(reply)
```

At the current implementation level, passive LIN sniffing is **not implemented**.
`logging_native` intentionally returns status 4 with
`passive RX unavailable` instead of inventing log data.

This is a prepared interface boundary. A future native passive receive queue can
be attached behind the same logging query pair without changing host
applications.

### Tap instances

For generic application-level observation, a runtime instance may be configured
with `tap=true`.

A tap receives copies of host frames after active-owner selection. It never
steals the active instance's message.

An empty tap channel list observes all user channels. A non-empty list acts as a
filter.

This is separate from passive electrical LIN sniffing.

## 12. Direct native MicroPython control

The standard runtime owns the MicroPython interpreter while it is running.
Direct `lin` module access is therefore a development/debug path.

Stop the runtime first:

```python
from beiis_lin.client import DaemonClient

c = DaemonClient()
c.runtime_call("runtime_stop")
print(c.exec("import lin; lin.init(1, 19200); print('ready')"))
c.close()
```

Native MicroPython examples:

```python
import lin

lin.init(1, 19200)

# Master publishes data.
lin.send(1, 0x12, b"\x11\x22\x33\x44", True)

# Master requests four data bytes from a slave.
data = lin.request(1, 0x22, 4, True)

# Configure this channel as slave responder.
lin.slave_set(2, 0x22, b"\x11\x22\x33\x44", True)
lin.slave_clear(2)

# Receive a master-published frame as slave.
lin.slave_rx_set(2, 0x12, 8, True)
data = lin.slave_rx_recv(2)       # bytes or None
```

The CLI wrappers `lin-init`, `lin-send`, `lin-request`,
`lin-slave-set` and `lin-slave-clear` use this Raw-REPL path. They are useful
for bring-up but are not replacements for the persistent query runtime.

## 13. Flashing firmware

There are two separate cases.

### Factory / first programming

Build bootloader and application:

```sh
make firmware-all
```

Program both through ST-Link/SWD:

```sh
make flash-swd
```

### Field update through I2C/mboot

Build the application:

```sh
make firmware
```

With no daemon owning I2C:

```sh
. .venv/bin/activate
beiis-lin --direct flash \
  build/micropython/ports/stm32/build-BEIIS_LIN_HAT/firmware.bin
```

Or use the Makefile field-update target:

```sh
make flash-i2c
```

If `beiis-lind` is running, use the socket path instead of opening I2C a
second time:

```sh
beiis-lin flash \
  build/micropython/ports/stm32/build-BEIIS_LIN_HAT/firmware.bin
```

The daemon-side flash operation receives a path on the same Linux host.

The application update erases/programs only the application flash region.
The MicroPython filesystem containing installed runtime apps and
`instances.json` is outside that application region and is therefore retained
by a normal application update.

Re-run `scripts/install-standard-runtime.py` only when the installed runtime
applications/configuration themselves need to change.

## 14. Python through the Unix socket

Use `DaemonClient`; do not open I2C from every application.

```python
from beiis_lin.client import DaemonClient

with_client = DaemonClient()
try:
    print(with_client.info())
    print(with_client.runtime_call("info"))

    with_client.set_active_instance(0)
    with_client.data_send(0, b"\x00")
    instance, channel, reply = with_client.data_recv(
        instance=1,
        channel=0,
        timeout=2.0,
    )
    print(instance, channel, reply.hex(" "))
finally:
    with_client.close()
```

A more complete executable example is
`examples/runtime/python_basic.py`.

## 15. C through the Unix socket

The socket is a normal Unix-domain `SOCK_SEQPACKET` endpoint. The wire format
is UTF-8 JSON. C applications do not need an I2C library.

Basic sequence:

1. `socket(AF_UNIX, SOCK_SEQPACKET, 0)`
2. connect to `/run/beiis/lin-hat.sock`
3. send one JSON request as one packet
4. receive one JSON reply packet
5. keep request IDs unique per connection

Example request:

```json
{"v":1,"id":1,"type":"request","op":"set_active_instance","args":{"instance":0}}
```

Send a native PING through `master_tx_query`:

```json
{"v":1,"id":2,"type":"request","op":"data_send","args":{"channel":0,"data":"00"}}
```

Receive its reply from `master_rx_query`:

```json
{"v":1,"id":3,"type":"request","op":"data_recv","args":{"instance":1,"channel":0,"timeout":2.0}}
```

The executable C example is `examples/runtime/c_basic.c`.

For production C code, use a real JSON parser. The supplied C file keeps parsing
minimal on purpose so the socket mechanics remain visible.

## 16. Host IRQ

STM32 PC6 is connected through the isolation stage to Raspberry Pi GPIO6.

The IRQ is level-based and represents pending host-visible work. Current sources
include:

- STM32 -> host application FIFO data,
- completed LIN1 slave receive,
- completed LIN2 slave receive.

`beiis-lind` uses the Linux GPIO character ABI v2. If GPIO event access is not
available, normal application receive falls back to polling.

The I2C count/status registers remain the source of truth; the GPIO is a wakeup
hint, not a replacement for transport framing.

## 17. Recommended application structure

For a normal application, keep this boundary:

```text
your C/Python program
        |
        | Unix socket only
        v
    beiis-lind
        |
        v
standard query pair
        |
        v
native/custom worker
```

Avoid mixing direct I2C, Raw REPL and the persistent runtime in the same normal
application.

Use direct I2C/Raw REPL for:

- first bring-up,
- firmware recovery,
- low-level diagnostics,
- developing a new native primitive.

Use the socket/runtime path for deployed applications.
