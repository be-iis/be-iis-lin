#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
import time

from beiis_lin.device import LinHat


DEFAULT_SIZES = (0, 1, 2, 3, 7, 8, 15, 16, 31, 32, 63, 64, 127, 128, 255, 256, 511, 512, 1023, 1024, 1536, 2048)
STRESS_SIZES = (0, 1, 7, 31, 128, 512, 2048)


def payload_for(sequence: int, size: int) -> bytes:
    return bytes(((sequence * 17 + index * 31 + size) & 0xFF) for index in range(size))


def wait_runtime(bus: int, address: int, timeout: float = 4.0) -> dict:
    deadline = time.monotonic() + timeout
    last_error = None
    while time.monotonic() < deadline:
        h = None
        try:
            h = LinHat(bus, address)
            caps = h.app_capabilities()
            if caps["protocol_version"] < 3:
                raise RuntimeError(
                    f"application protocol {caps['protocol_version']} is too old; expected >= 3"
                )
            info = h.runtime_call("info", timeout=0.5)
            return info
        except (OSError, TimeoutError, RuntimeError, ValueError) as exc:
            last_error = exc
            time.sleep(0.05)
        finally:
            if h is not None:
                h.close()
    raise TimeoutError(f"runtime did not become ready: {last_error!r}")


def require_echo_instance(info: dict, name: str) -> dict:
    for item in info.get("instances", []):
        if item.get("name") == name:
            if item.get("state") != "running":
                raise RuntimeError(
                    f"instance {name!r} is not running: state={item.get('state')!r}, "
                    f"error={item.get('error')!r}"
                )
            return item
    raise RuntimeError(f"runtime instance {name!r} not found")


def management_stress(h: LinHat, iterations: int) -> None:
    print(f"[1/5] management RPC stress: {iterations} calls")
    for i in range(iterations):
        selector = i % 4
        if selector == 0:
            result = h.runtime_call("active_instance", timeout=2.0)
            if not isinstance(result, int):
                raise RuntimeError(f"active_instance returned {result!r}")
        elif selector == 1:
            result = h.app_list()
            if not isinstance(result, list):
                raise RuntimeError(f"app_list returned {result!r}")
        elif selector == 2:
            result = h.instance_list()
            if not isinstance(result, list):
                raise RuntimeError(f"instance_list returned {result!r}")
        else:
            result = h.runtime_call("info", timeout=2.0)
            if result.get("runtime") != 1:
                raise RuntimeError(f"invalid runtime info: {result!r}")

        if (i + 1) % 50 == 0 or i + 1 == iterations:
            print(f"      {i + 1}/{iterations} OK")


def payload_boundaries(h: LinHat, slot: int, channel: int) -> None:
    print("[2/5] payload boundary sweep")
    for sequence, size in enumerate(DEFAULT_SIZES):
        payload = payload_for(sequence, size)
        h.data_send(channel, payload, timeout=2.0)
        instance, rx_channel, received = h.data_recv(
            instance=slot, channel=channel, timeout=2.0
        )
        if instance != slot or rx_channel != channel or received != payload:
            raise RuntimeError(
                f"echo mismatch at size {size}: "
                f"instance={instance}, channel={rx_channel}, len={len(received)}"
            )
        print(f"      {size:4d} bytes OK")


def echo_stress(h: LinHat, slot: int, channel: int, iterations: int) -> None:
    print(f"[3/5] echo stress: {iterations} packets")
    for i in range(iterations):
        size = STRESS_SIZES[i % len(STRESS_SIZES)]
        payload = payload_for(10000 + i, size)
        h.data_send(channel, payload, timeout=2.0)
        instance, rx_channel, received = h.data_recv(
            instance=slot, channel=channel, timeout=2.0
        )
        if instance != slot or rx_channel != channel or received != payload:
            raise RuntimeError(
                f"echo mismatch at packet {i}, size {size}: "
                f"instance={instance}, channel={rx_channel}, len={len(received)}"
            )
        if (i + 1) % 100 == 0 or i + 1 == iterations:
            print(f"      {i + 1}/{iterations} OK")


def lifecycle_cycles(bus: int, address: int, instance_name: str, cycles: int) -> None:
    print(f"[4/5] runtime stop/reset/autostart cycles: {cycles}")
    for i in range(cycles):
        h = LinHat(bus, address)
        try:
            result = h.runtime_stop()
            if result is not True:
                raise RuntimeError(f"runtime_stop returned {result!r}")

            # runtime_stop must return control to Raw REPL.
            out = h.exec("print('REPL')").strip()
            if out != "REPL":
                raise RuntimeError(f"unexpected Raw REPL response: {out!r}")

            # Native reset must work independently of the Raw REPL and restore
            # the autostart runtime.
            h.device_reset()
        finally:
            h.close()

        info = wait_runtime(bus, address)
        require_echo_instance(info, instance_name)
        print(f"      cycle {i + 1}/{cycles} OK")


def led_self_test(bus: int, address: int, instance_name: str) -> None:
    print("[5/5] LED GPIO/self-test")
    print("      WATCH BOARD: each LED will light individually for about 300 ms")
    h = LinHat(bus, address)
    try:
        result = h.runtime_stop()
        if result is not True:
            raise RuntimeError(f"runtime_stop before LED test returned {result!r}")

        code = """
import lin,time
_names=('LIN1 RX','LIN1 TX','LIN1 SLAVE','LIN1 MASTER','LIN2 RX','LIN2 TX','LIN2 SLAVE','LIN2 MASTER')
for _i in range(8):
    _mask=1<<_i
    _got=lin.leds(_mask)
    if _got!=_mask:
        raise RuntimeError('LED mask mismatch: got=%d expected=%d'%(_got,_mask))
    print(_names[_i])
    time.sleep_ms(300)
lin.leds(0)
if lin.leds()!=0:
    raise RuntimeError('LEDs did not return to off state')
print('LED_TEST_OK')
"""
        out = h.exec(code)
        if "LED_TEST_OK" not in out:
            raise RuntimeError(f"LED self-test did not complete: {out!r}")
        for line in out.splitlines():
            print(f"      {line}")

        h.device_reset()
    finally:
        h.close()

    info = wait_runtime(bus, address)
    require_echo_instance(info, instance_name)
    print("      runtime restored after LED test")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="BE-IIS LIN HAT application-runtime hardware regression test"
    )
    parser.add_argument("--bus", type=int, default=1)
    parser.add_argument("--address", type=lambda value: int(value, 0), default=0x42)
    parser.add_argument("--instance", default="echo")
    parser.add_argument("--channel", type=int, default=0)
    parser.add_argument("--management-iterations", type=int, default=200)
    parser.add_argument("--iterations", type=int, default=1000)
    parser.add_argument("--cycles", type=int, default=10)
    args = parser.parse_args()

    h = LinHat(args.bus, args.address)
    try:
        caps = h.app_capabilities()
        print("capabilities:", caps)
        if caps["protocol_version"] < 3:
            raise RuntimeError(
                f"application protocol {caps['protocol_version']} is too old; expected >= 3"
            )

        info = h.runtime_call("info", timeout=2.0)
        instance = require_echo_instance(info, args.instance)
        slot = int(instance["slot"])
        print(
            f"instance: {args.instance} slot={slot} "
            f"channel={args.channel} state={instance['state']}"
        )

        management_stress(h, args.management_iterations)
        payload_boundaries(h, slot, args.channel)
        echo_stress(h, slot, args.channel, args.iterations)
    finally:
        h.close()

    lifecycle_cycles(args.bus, args.address, args.instance, args.cycles)
    led_self_test(args.bus, args.address, args.instance)

    print()
    print("PASS: runtime + LED hardware regression completed successfully")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, TimeoutError, RuntimeError, ValueError) as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        raise SystemExit(1)
