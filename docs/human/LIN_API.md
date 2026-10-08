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

# Manufacturing / hardware self-test only:
mask = lin.leds()       # read active LED mask
mask = lin.leds(0x01)   # drive LED mask
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

LED self-test mask bits are: bit0 LIN1 RX, bit1 LIN1 TX, bit2 LIN1 slave,
bit3 LIN1 master, bit4 LIN2 RX, bit5 LIN2 TX, bit6 LIN2 slave, bit7 LIN2
master. The normal LIN API drives these LEDs automatically.
