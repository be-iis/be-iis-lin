# BE-IIS LIN HAT — MicroPython and firmware reference

**Firmware:** The LIN implementation is maintained on `main`. Key functions have been tested on a Raspberry Pi 5 with LIN1 and LIN2 connected.

The STM32G0B0 runs MicroPython 1.27.0 and a native C LIN engine. Each channel has its own UART, mode, configuration table, and completed-frame FIFO. Both channels share a 1 MHz monotonic TIC counter.

## Quick start

```bash
git clone https://github.com/be-iis/be-iis-lin.git
cd be-iis-lin
git switch main
bash scripts/prepare.sh
make host
make firmware-all
make test
```

Use the board at I²C address `0x42` on bus 1. Execute MicroPython directly:

```bash
./.venv/bin/beiis-lin --direct info
./.venv/bin/beiis-lin --direct exec "import lin; print(lin.tic())"
```

`beiis-lin --direct exec` has a **5-second default Raw-REPL result timeout**. For longer tests, use `run` only if the script terminates quickly, or adjust `RawRepl.exec(... timeout=...)` in `host/beiis_lin/raw_repl.py` (e.g. 30 seconds). Avoid flooding the 512-byte console FIFO with output.

## Complete MicroPython `lin` module API

| Command | Arguments | Result / notes |
|---|---|---|
| `lin.init(channel, baud)` | channel 1 or 2, baud 1000–20000 | Configures physical LIN UART |
| `lin.send(channel, id, data, enhanced=True)` | 6-bit ID 0x00–0x3F; 0–8 data bytes | Master publishes a frame; returns `None` |
| `lin.request(channel, id, length, enhanced=True)` | length 0–8 | Master requests slave response; returns `bytes`, verifies checksum |
| `lin.request_raw(channel, id, length)` | raw receive length 1–9 including checksum | Returns raw `bytes`, no checksum validation |
| `lin.slave_set(channel, id, data, enhanced=True)` | repeated for multiple IDs | Registers or replaces one slave response; 64 slots/channel |
| `lin.slave_clear(channel, id)` | specific ID | Removes one slave response |
| `lin.slave_clear(channel)` | channel | Removes all slave responses |
| `lin.sniffer_set(channel, id, length, enhanced=True)` | ID, expected data length 0–8 | Adds or replaces one passive monitoring rule |
| `lin.sniffer_clear(channel)` | channel | Clears all monitoring rules |
| `lin.sniffer(channel, True)` | channel | Enables passive-only sniffer (no slave IDs allowed) |
| `lin.sniffer(channel, False)` | channel | Disables sniffer, retains rules and FIFO data |
| `lin.recv(channel)` | channel | Pops oldest completed TX/RX frame dict or `None` |
| `lin.tic()` | none | Monotonic unsigned 64-bit microsecond time since firmware startup |

All operations run on the **STM32 MicroPython**. For host access use the CLI, which sends code over I²C Raw REPL. Invalid arguments or bus/timeouts raise `OSError` or `ValueError`.

### Modes and channel independence

A channel cannot be a sniffer and a master or slave simultaneously; the C firmware enforces this. Set slave rules only when sniffer is disabled. To start sniffing, remove slave rules first. The other channel can operate independently. `lin.init` sets the baud rate; it does not enable sniffer. Monitor rules are **selected IDs only**, each with an expected length and checksum type. Unknown IDs are ignored.

### Frame record and TIC

```python
frame = lin.recv(1)
# {'id': 18, 'len': 4, 'data': b'\x11\x22\x33\x44',
#  'tic_start': 434131546, 'tic_duration': 4817, 'status': 0}
if frame:
    tic_end = frame['tic_start'] + frame['tic_duration']
```

`tic_start` is 64-bit, `tic_duration` is 32-bit; both are measured in **microseconds**. The same 1 MHz TIM6-derived clock is shared by LIN1 and LIN2; rollover is extended in the native C firmware. TIC is **not Unix wall-clock time**. For correlation to UTC, read `lin.tic()` near a host clock sample and account for I²C latency and oscillator drift. Master timing is sampled around blocking UART operations, so it includes some software delay. Sniffer start is measured at LIN-break detection (not the first electrical edge); durations are based on USART receive events, not oscilloscope edges.

`status=0` denotes a valid frame; `status=1` a failed checksum in sniffer mode. The native FIFO stores 15 usable frames per channel; full FIFO discards the oldest frame. Failed/incomplete frames and arbitrary unconfigured IDs are **not yet guaranteed** to appear; passive monitoring is not a generic all-IDs analyzer.

## MicroPython examples

### Master and multiple slave IDs

```python
import lin
lin.init(1, 19200)
lin.init(2, 19200)
lin.slave_clear(2)
lin.slave_set(2, 0x12, b'\x11\x22\x33\x44')
lin.slave_set(2, 0x23, b'\x55\x66')
print(lin.request(1, 0x12, 4))
print(lin.request(1, 0x23, 2))
print(lin.recv(1))  # master timestamped record
print(lin.recv(2))  # slave timestamped record
lin.slave_clear(2, 0x23) # remaining ID stays active
```

### Selective passive monitor

```python
import lin
lin.init(1, 19200)
lin.init(2, 19200)
lin.slave_clear(2)
lin.sniffer_clear(2)
lin.sniffer_set(2, 0x12, 4)        # enhanced checksum
lin.sniffer_set(2, 0x23, 2, False) # classic checksum
lin.sniffer(2, True)
# On this loopback test board, channel 1 publishes selected IDs.
lin.send(1, 0x12, b'\x11\x22\x33\x44')
lin.send(1, 0x35, b'\xaa\xbb')   # ignored by channel 2
frame = lin.recv(2)
print(frame)
lin.sniffer(2, False)
```

### TIC benchmark

```python
import lin, time
a = lin.tic()
time.sleep_ms(150)
b = lin.tic()
print('elapsed_us', b - a)  # around 150000, across TIM6 overflows
```

### Long-running request logger

```python
import lin
lin.init(1, 19200)
for n in range(100):
    try:
        data = lin.request(1, 0x12, 4)
        frame = lin.recv(1)
        if frame:
            print(n, data, frame['tic_start'], frame['tic_duration'])
    except OSError as exc:
        print('request error', exc)
```

For continuous acquisition drain the FIFO promptly: it holds only 15 frames per channel. Host output should be rate limited.

## Built-in LEDs (no MicroPython LED commands)

The native C firmware drives **active-low** LED outputs, regardless of whether MicroPython is active.

| Indicator | LIN1 | LIN2 | Meaning |
|---|---|---|---|
| MASTER | PA6 | PA15 | Master transaction activity |
| SLAVE | PA10 | PB5 | Steady when at least one slave ID is configured |
| TX | PB1 | PB4 | Transmit activity |
| RX | PA5 | PB3 | Receive/break activity |

MASTER/TX/RX activity stays visible **at least 50 ms**; a TIM6 overflow checks expiry every 65.536 ms, so pulses may last about 50–116 ms. No LED control API is exposed.

## Firmware build, installation, update, recovery

The firmware consists of a **32 KiB mboot at 0x08000000** and an **application beginning at 0x08008000**. Initial programming uses ST-Link; normal application upgrades use I²C/mboot.

```bash
cd ~/be-iis-lin
git switch main
git pull --ff-only
make host
make firmware-all
make test
./.venv/bin/beiis-lin --direct info
./.venv/bin/beiis-lin --direct exec "import lin; print(lin.tic())"
make flash-i2c
```

`make flash-i2c` asks the **running MicroPython** to enter mboot, programs/verifies the application, and resets it. If Raw-REPL does not respond, the normal I²C procedure will fail; **do not erase mboot**. With a working ST-Link and a confirmed 0x08008000 application image, an application-only SWD recovery is possible:

```bash
sudo openocd -f interface/stlink.cfg -f target/stm32g0x.cfg \
  -c "transport select swd" -c "adapter speed 100" \
  -c "reset_config srst_only srst_nogate connect_assert_srst" \
  -c "init" -c "reset halt" \
  -c "flash write_image erase build/micropython/ports/stm32/build-BEIIS_LIN_HAT/firmware.hex" \
  -c "verify_image build/micropython/ports/stm32/build-BEIIS_LIN_HAT/firmware.hex" \
  -c "reset run" -c "shutdown"
```

Verify the HEX address range before flashing. Power-cycle the board if it remains halted under a debugger, then check `i2cdetect -y 1` and `./.venv/bin/beiis-lin --direct info`. ST-Link initial programming of both mboot and application is available via `make flash-swd`, but it modifies the bootloader and should **not** be used for routine updates.

## Hardware and limitations

MCU STM32G0B0KET6; LIN1 USART1 PB6/PB7, LIN2 USART2 PA2/PA3; Raspberry Pi I²C1 at 0x42. A working LIN bus needs appropriate bus power, pull-up, and common reference; connecting two test LIN terminals is appropriate only with matching hardware setup. Slave response tables, monitor rules, and FIFO data are volatile. LIN diagnostic transport, scheduler, sleep/wakeup, and passive capture of arbitrary unknown-length IDs are not provided. Additional regression testing is recommended for production deployment.
