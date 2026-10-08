# IP over LIN experiment

This directory is intentionally isolated from the production STM32 and
MicroPython runtime. IP is only one possible upper-layer experiment.

The experiment now uses the universal runtime instances instead of Raw REPL or
direct LIN socket operations.

```text
Linux IPv4 stack
        |
        v
lin0 (TUN)
        |
        v
bridge.py
        |
        v
beiis-lind Unix socket
        |
        v
master_tx_query -> master_native -> master_rx_query
        |
        v
LIN1
```

For the physical loopback test, LIN2 is driven through:

```text
slave_tx_query -> slave_native -> slave_rx_query
```

There is no IP-specific STM32 register set, MicroPython module, firmware code or
runtime instance.

## Prerequisites

The STM32 must run the 16-slot firmware and the standard runtime layout must be
installed:

```sh
python scripts/install-standard-runtime.py
```

LIN1 and LIN2 must be physically connected for the loopback test.

## Unit test

```sh
cd examples/ip-over-lin
../../.venv/bin/python -m unittest -v test_bridge.py
```

## Hardware test

From the repository root on the Raspberry Pi:

```sh
sudo examples/ip-over-lin/test-hardware.sh
```

The test starts a temporary `beiis-lind`, creates `lin0` at
`10.42.1.1/24`, and pings `10.42.1.2`.

The ICMP reply is still synthesized by the Linux experiment. Its LIN response
frames are installed on LIN2 through the slave runtime instances and physically
requested back on LIN1 through the master runtime instances. This tests the
runtime-instance data path end-to-end without putting IP knowledge into the
STM32.
