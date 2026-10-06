# LIN API

STM32 MicroPython module:

```python
import lin

lin.init(channel, baud)
lin.send(channel, frame_id, data, enhanced=True)
data = lin.request(channel, frame_id, length, enhanced=True)
raw = lin.request_raw(channel, frame_id, length)
lin.slave_set(channel, frame_id, data, enhanced=True)
lin.slave_clear(channel)
```

Current constraints:

- channels: 1 or 2
- frame ID: 0x00..0x3f
- payload: up to 8 bytes
- baud accepted by current implementation: 1000..20000
- request timeout currently fixed at 100 ms
- one slave response slot per channel
- no passive RX queue/sniffer yet
- no scheduler yet
- no LIN diagnostic transport abstraction yet
- sleep/wakeup API is not implemented yet

Both classic and enhanced checksum request/response paths have been verified on
hardware.
