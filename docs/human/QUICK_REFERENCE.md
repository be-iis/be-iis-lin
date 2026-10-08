# Quick reference

This page is the short operational reference. For explanations, see
`RUNTIME_GUIDE.md`.

## Standard runtime slots

| Function | TX query | RX query | Worker | Physical/resource |
|---|---:|---:|---:|---|
| master | 0 | 1 | 2 | LIN1 |
| slave | 3 | 4 | 5 | LIN2 |
| logging | 6 | 7 | 8 | logger control/status |

Free custom slots: 9..15.

## Start daemon

Development:

```sh
. .venv/bin/activate
beiis-lind \
  --socket /tmp/beiis-lin.sock \
  --lock-file /tmp/beiis-lind.lock
```

Check:

```sh
beiis-lin --socket /tmp/beiis-lin.sock info
```

## Native reply format

```text
byte 0  operation
byte 1  status
byte 2+ result
```

Status:

```text
0 OK
1 bad request
2 LIN error
3 internal error
4 unsupported (logging worker)
```

Enhanced checksum: flags bit0 = 1.  
Classic checksum: flags bit0 = 0.

## Native operations

```text
00                  PING
01 <baud u32-le>     INIT
02 id flags len data SEND
03 id flags len      REQUEST
04 id flags len data SLAVE_SET
05                  SLAVE_CLEAR
06                  LEDS_GET
07 mask             LEDS_SET
08 id flags len      SLAVE_RX_SET
09                  SLAVE_RX_RECV
```

## Python: master PING

```python
from beiis_lin.client import DaemonClient

c = DaemonClient()
c.set_active_instance(0)
c.data_send(0, b"\x00")
print(c.data_recv(instance=1, channel=0))
c.close()
```

Expected payload: `00 00`.

## Python: master transmit

LIN ID `0x12`, enhanced checksum, four bytes:

```python
request = bytes.fromhex("02 12 01 04 11 22 33 44")

c.set_active_instance(0)
c.data_send(0, request)
_, _, reply = c.data_recv(instance=1, channel=0)
```

Expected reply: `02 00`.

## Python: master request

Request four bytes from ID `0x22`:

```python
c.set_active_instance(0)
c.data_send(0, bytes.fromhex("03 22 01 04"))
_, _, reply = c.data_recv(instance=1, channel=0)
```

Reply example:

```text
03 00 04 11 22 33 44
```

## Python: configure slave response

```python
c.set_active_instance(3)
c.data_send(0, bytes.fromhex("04 22 01 04 11 22 33 44"))
_, _, reply = c.data_recv(instance=4, channel=0)
```

Clear:

```python
c.data_send(0, b"\x05")
_, _, reply = c.data_recv(instance=4, channel=0)
```

## Python: slave receive master-published frame

Configure ID `0x12`, eight bytes:

```python
c.set_active_instance(3)
c.data_send(0, bytes.fromhex("08 12 01 08"))
c.data_recv(instance=4, channel=0)
```

Fetch:

```python
c.data_send(0, b"\x09")
_, _, reply = c.data_recv(instance=4, channel=0)
```

## Logging

PING:

```python
c.set_active_instance(6)
c.data_send(0, b"\x00")
print(c.data_recv(instance=7, channel=0))
```

STATUS:

```python
c.data_send(0, b"\x01")
print(c.data_recv(instance=7, channel=0))
```

Passive LIN sniffing is not implemented yet.

## Executable examples

```sh
python examples/runtime/python_basic.py master-ping
python examples/runtime/python_basic.py master-send 0x12 11223344
python examples/runtime/python_basic.py master-request 0x22 4
python examples/runtime/python_basic.py slave-set 0x22 11223344
python examples/runtime/python_basic.py slave-clear
python examples/runtime/python_basic.py logging-status
```

## Custom query

```sh
python examples/runtime/install_custom_query.py
python examples/runtime/custom_query_client.py "hello world"
```

## C socket example

```sh
cc -O2 -Wall -Wextra examples/runtime/c_basic.c -o /tmp/beiis-runtime-c
/tmp/beiis-runtime-c
```

## Flash

Factory/full:

```sh
make firmware-all
make flash-swd
```

Application field update with daemon stopped:

```sh
make firmware
beiis-lin --direct flash \
  build/micropython/ports/stm32/build-BEIIS_LIN_HAT/firmware.bin
```

With daemon running:

```sh
beiis-lin flash \
  build/micropython/ports/stm32/build-BEIIS_LIN_HAT/firmware.bin
```

## Check examples

```sh
make -C examples/runtime check
```
