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

Install the systemd service:

```sh
sudo bash scripts/install-daemon.sh
```

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
