# Unix socket API

`beiis-lind` owns the HAT I2C endpoint and exposes a local Unix-domain
`SOCK_SEQPACKET` API.

Default socket:

```text
/run/beiis/lin-hat.sock
```

Protocol version: `1`.

## Packet framing

One Unix `SOCK_SEQPACKET` packet contains exactly one UTF-8 JSON object.
There is no additional length prefix.

Request:

```json
{
  "v": 1,
  "id": 1,
  "type": "request",
  "op": "ping",
  "args": {}
}
```

Successful reply:

```json
{
  "v": 1,
  "id": 1,
  "type": "reply",
  "ok": true,
  "result": {}
}
```

Error reply:

```json
{
  "v": 1,
  "id": 1,
  "type": "reply",
  "ok": false,
  "error": {
    "type": "ValueError",
    "message": "..."
  }
}
```

Long-running operations such as firmware flashing may emit event packets with
the same request ID before the final reply:

```json
{
  "v": 1,
  "id": 7,
  "type": "event",
  "event": "progress",
  "data": {
    "stage": "write",
    "done": 4096,
    "total": 100000
  }
}
```

Clients must keep receiving until the final `type="reply"` for their request
ID arrives.

Maximum socket packet size in the current host implementation is 1 MiB.

## Binary values

Binary application payloads are encoded as lowercase or uppercase hexadecimal
strings inside JSON.

Example bytes:

```text
11 22 33 44
```

JSON:

```json
"11223344"
```

## Core operations

### info

Request:

```json
{"v":1,"id":1,"type":"request","op":"info","args":{}}
```

Returns daemon protocol, device status and GPIO IRQ information.

### ping

```json
{"v":1,"id":2,"type":"request","op":"ping","args":{}}
```

Returns the native I2C protocol version/status.

## Runtime data operations

### data_info

```json
{"v":1,"id":3,"type":"request","op":"data_info","args":{}}
```

Returns application transport capabilities.

### active_instance

Read:

```json
{"v":1,"id":4,"type":"request","op":"active_instance","args":{}}
```

### set_active_instance

```json
{"v":1,"id":5,"type":"request","op":"set_active_instance","args":{"instance":0}}
```

Valid slot range is 0..15.

### data_send

```json
{"v":1,"id":6,"type":"request","op":"data_send","args":{"channel":0,"data":"020c01021122"}}
```

`channel` is 0..31. `data` is hexadecimal.

### data_recv

```json
{"v":1,"id":7,"type":"request","op":"data_recv","args":{"instance":1,"channel":0,"timeout":2.0}}
```

`instance` and `channel` may be JSON `null` to accept any source.

Successful result:

```json
{
  "instance": 1,
  "channel": 0,
  "data": "0200"
}
```

## Runtime management

The outer socket operation is `runtime`. The inner operation is handled by the
STM32 runtime management channel.

Example:

```json
{
  "v": 1,
  "id": 8,
  "type": "request",
  "op": "runtime",
  "args": {
    "op": "info",
    "args": {},
    "timeout": 2.0
  }
}
```

Implemented inner operations include:

- `info`
- `app_list`
- `install_begin`
- `install_chunk`
- `install_commit`
- `app_remove`
- `instance_add`
- `instance_remove`
- `instance_configure`
- `instance_list`
- `active_instance`
- `start`
- `stop`
- `restart`
- `autostart`
- `runtime_stop`

See `protocol/APP-RUNTIME.md` for the STM32-side model.

## Flash and recovery operations

Socket operations:

- `enter_bootloader`
- `mboot_info`
- `mboot_reset`
- `flash`

Flash request:

```json
{
  "v": 1,
  "id": 9,
  "type": "request",
  "op": "flash",
  "args": {
    "path": "/home/pi/be-iis-lin/firmware.bin"
  }
}
```

The path is resolved by `beiis-lind` on the same Linux host.

## Direct Raw-REPL LIN operations

The daemon also exposes:

- `lin_init`
- `lin_send`
- `lin_request`
- `lin_slave_set`
- `lin_slave_clear`

These call the MicroPython `lin` module through Raw REPL. They are intended for
bring-up/debug after the persistent runtime has been stopped.

Normal deployed applications should use `data_send`/`data_recv` through a
query/native/query path instead.

## GPIO wait operations

`wait_irq` and `drain_irq` exist for host-side coordination.

They are normally implementation details. Applications should usually block on
`data_recv`; the host transport uses GPIO6 automatically when available.

## C clients

C clients should use:

```c
socket(AF_UNIX, SOCK_SEQPACKET, 0);
```

and preserve one JSON object per socket packet.

See `examples/runtime/c_basic.c`.

## Python clients

Python applications should normally use `beiis_lin.client.DaemonClient`
instead of creating JSON manually.

See `examples/runtime/python_basic.py`.
