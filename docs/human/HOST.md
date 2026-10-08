# Linux host

## Daemon

`beiis-lind` owns the HAT I2C endpoint and exposes a local Unix
`SOCK_SEQPACKET` socket.

Default production socket:

```text
/run/beiis/lin-hat.sock
```

For development it can be started manually:

```sh
. .venv/bin/activate
beiis-lind --bus 1 --address 0x42 \
  --socket /tmp/beiis-lin.sock \
  --lock-file /tmp/beiis-lind.lock
```

The repository does not install a systemd service. Start `beiis-lind` explicitly
when a socket backend is required.

## CLI

```sh
beiis-lin info
beiis-lin ping
beiis-lin lin-init 1 19200
beiis-lin lin-send 1 0x22 11223344
beiis-lin lin-request 1 0x22 4
beiis-lin lin-slave-set 2 0x22 11223344
beiis-lin lin-slave-clear 2
```

Add `--classic` to LIN send/request/slave-set for classic checksum. Enhanced
checksum is the default.

If the daemon socket exists the CLI uses it. `--direct` bypasses the daemon
and accesses I2C directly; this is intended for development and recovery.


## Application runtime through the daemon

The same Unix socket also carries application-runtime management and framed
application data. Python applications can use `DaemonClient`:

```python
from beiis_lin.client import DaemonClient

c = DaemonClient()
try:
    print(c.data_info())
    print(c.runtime_call("info"))

    c.data_send(0, b"hello")
    instance, channel, data = c.data_recv(timeout=2.0)
finally:
    c.close()
```

The runtime management path, application data path, bidirectional LIN traffic,
native mboot entry and return to the autostart runtime have all been verified
end-to-end through `beiis-lind` on hardware.

## Ownership and recovery

In production, `beiis-lind` should be the only process accessing the HAT I2C
address. `--direct` is intended for bring-up and recovery when the daemon is
stopped.

Application protocol v3 provides native control operations that remain
available even if the MicroPython interpreter is busy:

- application FIFO reset,
- direct entry into mboot,
- STM32 system reset.

The host uses the native mboot path for field updates, so firmware updates do
not depend on Raw REPL availability.

## Network access

`beiis-lind` currently listens on a local Unix `SOCK_SEQPACKET` socket only.
It does not open a TCP port and should not be exposed with an unauthenticated
TCP-to-Unix bridge.

For LAN testing, use the SSH stream-local forwarding procedure in
`LAN_TEST.md`. This preserves the same daemon/socket protocol while SSH
provides transport security and host authentication.


## Host IRQ

On Raspberry Pi hardware, `beiis-lind` uses GPIO6 by default as the isolated
STM32 host-notification input.

The daemon accesses the GPIO directly through Linux GPIO character ABI v2 and
does not require a Python `gpiod` package.

Default:

```sh
.venv/bin/beiis-lind --irq-gpio 6
```

An explicit GPIO chip name/path may be supplied with `--irq-chip`. The daemon
automatically prefers RP1/pinctrl GPIO chips when no chip is specified.

To force the compatibility polling path:

```sh
.venv/bin/beiis-lind --no-irq
```

If GPIO acquisition fails, the normal daemon continues with polling and reports
the reason in its `info` reply. Hardware performance tests require the IRQ to
be active so a polling run cannot be mistaken for an interrupt-driven result.
