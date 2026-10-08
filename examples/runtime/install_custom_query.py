#!/usr/bin/env python3
from __future__ import annotations

import binascii
from pathlib import Path

from beiis_lin.client import DaemonClient


ROOT = Path(__file__).resolve().parent
APP_NAME = "custom_query_worker"
INSTANCE_NAMES = ("custom_tx_query", "custom_rx_query", "custom_native")


def install_app(c: DaemonClient, path: Path) -> None:
    data = path.read_bytes()
    c.runtime_call("install_begin", {"app": APP_NAME, "size": len(data)}, timeout=5.0)

    for offset in range(0, len(data), 384):
        chunk = data[offset:offset + 384]
        c.runtime_call(
            "install_chunk",
            {"app": APP_NAME, "data": chunk.hex()},
            timeout=5.0,
        )

    crc = binascii.crc32(data) & 0xFFFFFFFF
    c.runtime_call(
        "install_commit",
        {"app": APP_NAME, "crc32": crc},
        timeout=5.0,
    )


def main() -> int:
    c = DaemonClient()
    try:
        apps = c.runtime_call("app_list")
        if "query" not in apps:
            raise RuntimeError(
                "standard query app is not installed; run scripts/install-standard-runtime.py"
            )

        existing = {
            item["name"]: item
            for item in c.runtime_call("instance_list")
        }

        for name in reversed(INSTANCE_NAMES):
            if name in existing:
                print("remove", name)
                c.runtime_call("instance_remove", {"name": name})

        install_app(c, ROOT / "custom_query_worker.py")

        tx = c.runtime_call(
            "instance_add",
            {
                "name": "custom_tx_query",
                "app": "query",
                "channels": [0],
                "config": {"direction": "tx", "peer": "custom_native"},
                "autostart": True,
                "resources": [],
                "tap": False,
            },
        )
        rx = c.runtime_call(
            "instance_add",
            {
                "name": "custom_rx_query",
                "app": "query",
                "channels": [],
                "config": {"direction": "rx", "peer": "custom_native"},
                "autostart": True,
                "resources": [],
                "tap": False,
            },
        )
        native = c.runtime_call(
            "instance_add",
            {
                "name": "custom_native",
                "app": APP_NAME,
                "channels": [],
                "config": {
                    "tx_peer": "custom_tx_query",
                    "rx_peer": "custom_rx_query",
                },
                "autostart": True,
                "resources": [],
                "tap": False,
            },
        )

        # instance_add persists configuration but does not start a newly-added
        # instance in the already-running runtime.
        for name in INSTANCE_NAMES:
            c.runtime_call("start", {"name": name})

        print("installed:")
        print("  custom_tx_query slot", tx["slot"])
        print("  custom_rx_query slot", rx["slot"])
        print("  custom_native   slot", native["slot"])
        return 0
    finally:
        c.close()


if __name__ == "__main__":
    raise SystemExit(main())
