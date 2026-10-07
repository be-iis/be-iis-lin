# LAN hardware test

`beiis-lind` intentionally exposes only a local Unix `SOCK_SEQPACKET` socket.
The first LAN regression therefore uses OpenSSH stream-local forwarding instead
of adding an unauthenticated TCP listener.

This tests the real path:

```text
remote Linux test host
        |
        | DaemonClient / Unix SOCK_SEQPACKET
        v
local forwarded Unix socket
        |
        | SSH over Ethernet/WLAN
        v
Raspberry Pi
        |
        | /run/beiis/lin-hat.sock
        v
beiis-lind -> I2C -> STM32 -> LIN1/LIN2
```

The STM32 and `beiis-lind` do not need any LAN-specific changes.

## Prerequisites

On the Raspberry Pi:

- the current firmware is installed,
- `beiis-lind.service` is running,
- `/run/beiis/lin-hat.sock` exists,
- SSH access from the remote test host works.

On the remote Linux test host:

```sh
git clone https://github.com/be-iis/be-iis-lin.git
cd be-iis-lin
bash scripts/prepare.sh
make host
```

The remote host needs only the Python client package and OpenSSH. It does not
need I2C hardware.

## Run

From the remote test host:

```sh
make test-lan-hw LAN_TARGET=philipp@pi5
```

Use the actual SSH destination for `LAN_TARGET`, for example an IP address:

```sh
make test-lan-hw LAN_TARGET=philipp@192.168.1.50
```

Optional overrides:

```sh
LAN_REMOTE_SOCKET=/run/beiis/lin-hat.sock \
LAN_LOCAL_SOCKET=/tmp/beiis-lin-lan.sock \
make test-lan-hw LAN_TARGET=philipp@pi5
```

The helper creates a temporary local Unix socket forwarded by SSH to the Pi
socket and runs `scripts/test-socket-hw.py` against that socket. The forward
is removed automatically when the test exits.

## Expected result

The existing socket hardware regression is executed over the LAN. In particular
it verifies:

- daemon info/ping,
- runtime management,
- application echo data including 2048-byte payloads,
- Raw REPL transition,
- LIN1 master -> LIN2 slave,
- LIN2 master -> LIN1 slave,
- native mboot entry/reset,
- runtime autostart after recovery.

Success ends with:

```text
PASS: Unix-socket hardware regression completed successfully
```

## Security note

Do not expose `/run/beiis/lin-hat.sock` through a plain `socat TCP-LISTEN`
bridge on an untrusted network. The daemon can control LIN hardware, enter
mboot and update firmware. SSH forwarding supplies host authentication,
encryption and access control for this test.

A native TCP/TLS transport, if added later, should be designed as a separate
authenticated interface rather than silently changing the Unix-socket security
model.
