#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
import time

from beiis_lin.client import DaemonClient, DaemonError


def wait_runtime(socket_path: str, timeout: float = 5.0) -> dict:
    deadline = time.monotonic() + timeout
    last_error = None
    while time.monotonic() < deadline:
        c = None
        try:
            c = DaemonClient(socket_path)
            info = c.runtime_call("info", timeout=0.5)
            if info.get("runtime") == 1:
                return info
        except (OSError, TimeoutError, RuntimeError, ValueError, DaemonError) as exc:
            last_error = exc
            time.sleep(0.05)
        finally:
            if c is not None:
                c.close()
    raise TimeoutError(f"runtime did not return through socket: {last_error!r}")


def require_echo(info: dict, name: str) -> dict:
    for item in info.get("instances", []):
        if item.get("name") == name:
            if item.get("state") != "running":
                raise RuntimeError(
                    f"instance {name!r} not running: "
                    f"state={item.get('state')!r} error={item.get('error')!r}"
                )
            return item
    raise RuntimeError(f"instance {name!r} not found")


def main() -> int:
    p = argparse.ArgumentParser(description="BE-IIS LIN HAT Unix-socket hardware regression")
    p.add_argument("--socket", default="/run/beiis/lin-hat.sock")
    p.add_argument("--instance", default="echo")
    p.add_argument("--echo-packets", type=int, default=100)
    args = p.parse_args()

    print("[1/5] connect / daemon info")
    c = DaemonClient(args.socket)
    try:
        info = c.info()
        ping = c.ping()
        data_info = c.data_info()
        print("      info:", info)
        print("      ping:", ping)
        print("      data:", data_info)
        if info.get("daemon_protocol") != 1:
            raise RuntimeError(f"unexpected daemon protocol: {info!r}")
        if data_info.get("protocol_version", 0) < 3:
            raise RuntimeError(f"application protocol too old: {data_info!r}")

        print("[2/5] runtime management through socket")
        rt = c.runtime_call("info")
        echo = require_echo(rt, args.instance)
        slot = int(echo["slot"])
        apps = c.runtime_call("app_list")
        instances = c.runtime_call("instance_list")
        active = c.active_instance()
        print("      apps:", apps)
        print("      instances:", instances)
        print("      active instance:", active)

        print(f"[3/5] application echo through socket: {args.echo_packets} packets")
        sizes = (0, 1, 7, 31, 128, 512, 2048)
        for i in range(args.echo_packets):
            size = sizes[i % len(sizes)]
            payload = bytes(((i * 19 + j * 29 + size) & 0xff) for j in range(size))
            c.data_send(0, payload)
            rx_instance, rx_channel, received = c.data_recv(
                instance=slot, channel=0, timeout=2.0
            )
            if (rx_instance, rx_channel, received) != (slot, 0, payload):
                raise RuntimeError(
                    f"socket echo mismatch packet={i} size={size} "
                    f"instance={rx_instance} channel={rx_channel} len={len(received)}"
                )
        print("      echo OK")

        print("[4/5] Raw REPL + bidirectional LIN through socket")
        if c.runtime_call("runtime_stop") is not True:
            raise RuntimeError("runtime_stop did not return True")
        repl = c.exec("print('SOCKET_REPL')").strip()
        if repl != "SOCKET_REPL":
            raise RuntimeError(f"unexpected REPL result: {repl!r}")
        print("      Raw REPL OK")

        c.lin_init(1, 19200)
        c.lin_init(2, 19200)

        c.lin_slave_set(2, 0x12, b"\x11\x22\x33\x44", enhanced=True)
        got = c.lin_request(1, 0x12, 4, enhanced=True)
        c.lin_slave_clear(2)
        if got != b"\x11\x22\x33\x44":
            raise RuntimeError(f"LIN1->LIN2 socket mismatch: {got!r}")
        print("      LIN1 master -> LIN2 slave OK")

        c.lin_slave_set(1, 0x22, b"\x55\x66\x77", enhanced=False)
        got = c.lin_request(2, 0x22, 3, enhanced=False)
        c.lin_slave_clear(1)
        if got != b"\x55\x66\x77":
            raise RuntimeError(f"LIN2->LIN1 socket mismatch: {got!r}")
        print("      LIN2 master -> LIN1 slave OK")

        print("[5/5] native mboot path through socket + runtime restore")
        c.bootloader()
        mboot = c.mboot_info()
        print("      mboot:", mboot)
        if mboot.get("board") != "BE-IIS LIN HAT":
            raise RuntimeError(f"unexpected mboot board: {mboot!r}")
        c.mboot_reset()
    finally:
        c.close()

    rt = wait_runtime(args.socket)
    require_echo(rt, args.instance)
    print("      runtime restored")

    print()
    print("PASS: Unix-socket hardware regression completed successfully")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, TimeoutError, RuntimeError, ValueError, DaemonError) as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        raise SystemExit(1)
