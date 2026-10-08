#!/usr/bin/env python3
from __future__ import annotations

import argparse

from beiis_lin.client import DaemonClient


def slot_by_name(info: dict, name: str) -> int:
    for item in info.get("instances", []):
        if item.get("name") == name:
            if item.get("state") != "running":
                raise RuntimeError(
                    f"{name} is not running: state={item.get('state')} error={item.get('error')}"
                )
            return int(item["slot"])
    raise RuntimeError(f"missing instance: {name}")


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("message", nargs="?", default="hello")
    p.add_argument("--socket", default="/run/beiis/lin-hat.sock")
    args = p.parse_args()

    c = DaemonClient(args.socket)
    try:
        info = c.runtime_call("info")
        tx_slot = slot_by_name(info, "custom_tx_query")
        rx_slot = slot_by_name(info, "custom_rx_query")

        c.set_active_instance(tx_slot)
        c.data_send(0, args.message.encode())

        instance, channel, payload = c.data_recv(
            instance=rx_slot,
            channel=0,
            timeout=2.0,
        )
        print(payload.decode("utf-8", "replace"))
        return 0
    finally:
        c.close()


if __name__ == "__main__":
    raise SystemExit(main())
