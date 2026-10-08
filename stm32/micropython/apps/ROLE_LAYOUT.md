# Standard runtime instance layout

The runtime has 16 slots. The standard layout uses nine instances and three
reusable application implementations.

| Slot | Instance | App | Configuration |
|---:|---|---|---|
| 0 | `master_tx_query` | `query` | tx -> `master_native` |
| 1 | `master_rx_query` | `query` | rx <- `master_native` |
| 2 | `master_native` | `lin_native` | LIN1, 19200 baud |
| 3 | `slave_tx_query` | `query` | tx -> `slave_native` |
| 4 | `slave_rx_query` | `query` | rx <- `slave_native` |
| 5 | `slave_native` | `lin_native` | LIN2, 19200 baud |
| 6 | `logging_tx_query` | `query` | tx -> `logging_native` |
| 7 | `logging_rx_query` | `query` | rx <- `logging_native` |
| 8 | `logging_native` | `logging_native` | logger control/status |
| 9..15 | free | - | reserved |

The central dispatcher remains part of `beiis_runtime.py`; it is not another
instance.

## Universal application boundary

The query instances are pure communication endpoints:

```text
host/application
      |
      v
*_tx_query
      |
      v
*_native
      |
      v
*_rx_query
      |
      v
host/application
```

All six query instances use the same `query.py`. Master and slave both use the
same `lin_native.py`; the configured LIN channel is the only difference.

The payload above this boundary is application-agnostic. `lin_native.py`
exposes generic binary LIN operations only.

## Generic LIN RPC

Request byte 0 is the operation. Replies echo the operation in byte 0 and carry
a status byte in byte 1.

Operations:

- `0x00` PING
- `0x01` INIT, followed by baud as u32 little-endian
- `0x02` SEND, followed by id, flags, length, data
- `0x03` REQUEST, followed by id, flags, requested length
- `0x04` SLAVE_SET, followed by id, flags, length, data
- `0x05` SLAVE_CLEAR
- `0x06` LEDS_GET
- `0x07` LEDS_SET, followed by mask

Flag bit 0 selects enhanced checksum; clear selects classic checksum.

Status values:

- `0` success
- `1` malformed/unsupported request
- `2` LIN/native error
- `3` internal worker error

## Logging

The logging topology is already present and uses the same query endpoints.
Passive LIN RX/sniffing is not yet available in the native LIN module, so
`logging_native` reports that capability as unavailable instead of fabricating
log data. The host/application interface can stay unchanged when native passive
RX is added later.

## Installation

After flashing firmware that supports 16 runtime slots:

```sh
python scripts/install-standard-runtime.py
```

The installer writes the three reusable application modules, removes the old
instance layout, creates the nine instances in slots 0 through 8, enables
autostart, selects slot 0 and resets the STM32.
