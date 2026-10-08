# IP over LIN experiment

This directory contains the complete IP-over-LIN experiment. Nothing in the
STM32 runtime knows about IP; the firmware exposes only generic LIN operations.

## Topology

The hardware loopback test creates two real Linux layer-3 endpoints on the Pi:

```text
root namespace                         beiis-lin-node2 namespace

10.42.1.1/24                           10.42.1.2/24
lin0                                   lin-node2
    |                                      ^
    v                                      |
bridge.py                              bridge.py
    |                                      ^
    v                                      |
master_tx_query                       slave_rx_query
    |                                      ^
    v                                      |
master_native                         slave_native
    |                                      ^
    v                                      |
  LIN1  =============================  LIN2
```

LIN1 and LIN2 must be physically connected.

The second endpoint is a normal Linux network namespace, so ICMP, TCP and UDP
are handled by the Linux network stack. The bridge does not synthesize ICMP
responses.

## LIN identifier mapping

A LIN frame identifier cannot simultaneously mean "master publishes data" and
"slave responds to a request". The experiment therefore uses two identifiers
per logical node:

```text
master -> node x:  x
node x -> master:  x | 0x20
```

For node 2:

```text
downlink: 0x02
uplink:   0x22
```

This currently gives logical node numbers 2 through 31.

Each 8-byte LIN payload carries:

```text
byte 0    START/END flags + 6-bit packet sequence
byte 1    fragment index
byte 2..7 six bytes of the IPv4 packet
```

## Prerequisites

The STM32 must run the current 16-slot firmware and the standard nine runtime
instances:

```sh
python scripts/install-standard-runtime.py
```

The new generic slave receive operations must be present in the firmware:

- `slave_rx_set`
- `slave_rx_recv`

For the throughput part, `iperf3` must be installed on the Pi.

## Unit test

From the repository root:

```sh
.venv/bin/python -m unittest -v examples/ip-over-lin/test_bridge.py
```

or:

```sh
make -C examples/ip-over-lin unit
```

## Full hardware test

```sh
sudo bash examples/ip-over-lin/test-hardware.sh
```

The script:

1. starts a temporary `beiis-lind`,
2. creates `lin0 = 10.42.1.1/24`,
3. creates namespace `beiis-lin-node2`,
4. creates `lin-node2 = 10.42.1.2/24` inside that namespace,
5. verifies three real ICMP echo requests,
6. starts `iperf3 -s` inside the node namespace,
7. runs a short TCP `iperf3` client through LIN.

For a ping-only run when iperf3 is unavailable:

```sh
sudo RUN_IPERF=0 bash examples/ip-over-lin/test-hardware.sh
```

The throughput is expected to be low in the first implementation because every
6-byte packet fragment currently crosses the userspace/runtime RPC path
individually. The purpose of this test is correctness and measurement of the
current baseline.
