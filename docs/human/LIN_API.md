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

# TIC and completed-frame FIFO
now_us = lin.tic()              # 64-bit microseconds since STM32 startup
frame = lin.recv(channel)       # oldest completed frame, or None
if frame:
    print(frame['tic_start'])    # 64-bit microseconds
    print(frame['tic_duration']) # 32-bit microseconds
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

## Monotonic TIC (experimental branch)

TIM6 is reserved by the firmware as a free-running 1 MHz clock. Its 16-bit
rollover interrupt extends the clock to a 64-bit monotonic microsecond count.
Both LIN channels share the same epoch; the clock starts during STM32
application initialization and is unrelated to Linux wall-clock time.

`lin.recv(channel)` drains a completed-frame ring buffer (16 slots per
channel, 15 usable entries). A full queue discards the oldest frame.
Each dictionary contains `id`, `len`, `data`, `tic_start`,
`tic_duration`. Master transmissions, successful master requests and
completed slave responses enter the queue. The existing `lin.send()` and
`lin.request()` return values remain unchanged.

**Current scope / limitations:**
- Passive sniffing and arbitrary master-published slave RX frames are not
  implemented. The queue only contains supported completed operations.
- Raw master requests do not create a completed-frame entry.
- Failed requests (timeout/checksum error) do not currently enter the queue.
- For master transactions, `tic_start` is sampled just before initiating
  the LIN break and the end after the blocking UART completion; therefore
  durations include a small software overhead. On slave replies the start is
  captured at the USART break-detection ISR and the end at TX complete.
- A LIN break-detection event occurs after the physical start of break.
  Timestamps are UART-event timings, not logic-analyzer edge captures.
- The application must leave TIM6 reserved; do not use `machine.Timer(6)`.

### Bench validation before merging

1. Build: `make firmware-all`; run `make test` for host regression.
2. Flash a spare/test STM32 only: `make flash-i2c`.
3. Read `lin.tic()` twice with a known delay; confirm elapsed microseconds
   and monotonically increasing values across multiple TIM6 rollovers
   (one occurs every 65.536 ms).
4. Initialize both buses and perform a master send / master request.
   Verify `lin.recv(1)` returns a frame with `tic_duration > 0` and
   `lin.recv(1)` subsequently returns `None`.
5. Use LIN1 master / LIN2 slave as in existing end-to-end test and verify
   both channels' timestamps share the same increasing clock.
6. Exercise back-to-back frames, queue overflow, baud rates and
   unexpected/invalid frames before considering the feature production-ready.

## Native LIN activity LEDs (experimental feature branch)

The STM32 C firmware owns all eight active-low LED pins. MicroPython does not
need to service them. Activity LEDs have a minimum visible on-time of 50 ms;
TIM6 periodically turns them off (actual on-time may be up to ~116 ms).

| LED | LIN1 | LIN2 | Meaning |
|---|---|---|---|
| MASTER | PA6 | PA15 | Master transaction activity pulse |
| SLAVE | PA10 | PB5 | Constant while a slave response is configured |
| TX | PB1 | PB4 | Master send/request header or slave-response TX pulse |
| RX | PA5 | PB3 | Master response reception or slave break detected |

LEDs are hardware indicators, not measured-edge captures. The actual blink
behavior must be confirmed on hardware before merging into main.

## Multi-ID slave and passive filtered sniffer (feature branch)

One LIN channel may respond as a slave on **multiple configured IDs**:

```python
lin.init(2, 19200)
lin.slave_set(2, 0x12, b'\x11\x22\x33\x44')
lin.slave_set(2, 0x23, b'\x55\x66')
lin.slave_clear(2, 0x12)  # Remove only ID 0x12
lin.slave_clear(2)        # Remove all slave IDs
```

Slave mode and sniffer mode are exclusive per channel. The sniffer is
receive-only and stores **only configured IDs**, with expected data lengths
and checksum modes. The two channels have independent configurations.

```python
lin.init(1, 19200)
lin.sniffer_set(1, 0x12, 4)        # enhanced checksum (default)
lin.sniffer_set(1, 0x23, 2, False) # classic checksum
lin.sniffer(1, True)
frame = lin.recv(1)               # or None if FIFO empty
lin.sniffer(1, False)             # stop, retain rules and queued frames
lin.sniffer_clear(1)              # remove all sniffer rules
```

The returned frame dict adds `status`: 0 means checksum correct; 1 means
checksum mismatch. The FIFO retains `tic_start` and `tic_duration`.
Frames for unconfigured IDs are ignored. A configured entry requires an exact
data length: an incomplete response is not yet reported as a frame.
Sniffer mode must be explicitly stopped before `lin.slave_set`; master
operations on an active slave/sniffer channel are rejected. Configurations
are volatile and lost on reset.

### Hardware validation before release

1. Compile `make firmware` and run `make test`; do not merge until verified.
2. Verify two different slave IDs on LIN2 respond independently to LIN1 master.
3. Remove one ID, then verify the other continues working.
4. Activate sniffer on idle LIN2 and send configured frames from LIN1;
   check data, checksum status and timestamps.
5. Verify an unconfigured ID does not appear in the sniffer FIFO.
6. Verify sniffer+slave on the same channel is rejected, and a master request
   while sniffing fails without disrupting I2C.
7. Test both directions, 0-byte and 8-byte frames, checksum failures,
   FIFO overflow and repeated mode changes.
