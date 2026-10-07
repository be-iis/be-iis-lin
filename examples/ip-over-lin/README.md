# IP over LIN experiment

This directory is intentionally isolated from the production STM32 and
MicroPython runtime.

Architecture:

```text
Linux IPv4 stack
        |
        v
lin0 (TUN, layer 3)
        |
        v
bridge.py
        |
        v
existing beiis-lind Unix SOCK_SEQPACKET API
        |
        v
existing STM32 / LIN stack
```

There is no IP-specific STM32 register set, no IP-specific MicroPython module,
and no IP-specific firmware code.

The experiment maps the last IPv4 octet to the LIN node ID. The current test
uses `10.42.1.1` for the master and `10.42.1.2` for node 2.

## Unit test

```sh
cd examples/ip-over-lin
../../.venv/bin/python -m unittest -v test_bridge.py
```

## Hardware loopback test

Connect LIN1 and LIN2 physically, then run from the repository root:

```sh
sudo examples/ip-over-lin/test-hardware.sh
```

The hardware test starts a temporary `beiis-lind` socket backend, creates
`lin0`, and runs three ICMP echo requests. The verified test result was 3/3
replies with 0% packet loss.

The first loopback test synthesizes the ICMP reply in the Linux bridge and
returns it through the physical LIN2 -> LIN1 response path. It is an experiment,
not part of the production MicroPython runtime.
