#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

from beiis_lin.device import LinHat


ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "stm32" / "micropython" / "apps"

STANDARD_INSTANCES = [
    {
        "name": "master_tx_query",
        "app": "query",
        "channels": [0],
        "config": {"direction": "tx", "peer": "master_native"},
        "resources": [],
    },
    {
        "name": "master_rx_query",
        "app": "query",
        "channels": [],
        "config": {"direction": "rx", "peer": "master_native"},
        "resources": [],
    },
    {
        "name": "master_native",
        "app": "lin_native",
        "channels": [],
        "config": {
            "tx_peer": "master_tx_query",
            "rx_peer": "master_rx_query",
            "lin_channel": 1,
            "baud": 19200,
        },
        "resources": ["lin1"],
    },
    {
        "name": "slave_tx_query",
        "app": "query",
        "channels": [0],
        "config": {"direction": "tx", "peer": "slave_native"},
        "resources": [],
    },
    {
        "name": "slave_rx_query",
        "app": "query",
        "channels": [],
        "config": {"direction": "rx", "peer": "slave_native"},
        "resources": [],
    },
    {
        "name": "slave_native",
        "app": "lin_native",
        "channels": [],
        "config": {
            "tx_peer": "slave_tx_query",
            "rx_peer": "slave_rx_query",
            "lin_channel": 2,
            "baud": 19200,
        },
        "resources": ["lin2"],
    },
    {
        "name": "logging_tx_query",
        "app": "query",
        "channels": [0],
        "config": {"direction": "tx", "peer": "logging_native"},
        "resources": [],
    },
    {
        "name": "logging_rx_query",
        "app": "query",
        "channels": [],
        "config": {"direction": "rx", "peer": "logging_native"},
        "resources": [],
    },
    {
        "name": "logging_native",
        "app": "logging_native",
        "channels": [],
        "config": {
            "tx_peer": "logging_tx_query",
            "rx_peer": "logging_rx_query",
        },
        "resources": [],
    },
]


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Install the standard 9-instance BE-IIS LIN runtime layout"
    )
    parser.add_argument("--bus", type=int, default=1)
    parser.add_argument("--address", type=lambda value: int(value, 0), default=0x42)
    args = parser.parse_args()

    h = LinHat(args.bus, args.address)
    try:
        info = h.runtime_call("info", timeout=2.0)
        max_instances = int(info.get("max_instances", 0))
        if max_instances < 9:
            raise RuntimeError(
                f"firmware supports only {max_instances} instances; flash the 16-slot firmware first"
            )

        print("Installing universal runtime applications ...")
        for app in ("query", "lin_native", "logging_native"):
            path = APP_DIR / f"{app}.py"
            print(f"  {app} <- {path}")
            h.app_install(path, app=app, timeout=5.0)

        existing = list(h.instance_list())
        if existing:
            print("Removing existing instances ...")
        # Remove all configured instances so standard slots are deterministic.
        for item in reversed(existing):
            name = str(item["name"])
            print(f"  remove {name}")
            h.instance_remove(name)

        print("Creating standard runtime layout ...")
        for expected_slot, spec in enumerate(STANDARD_INSTANCES):
            created = h.instance_add(
                spec["name"],
                spec["app"],
                channels=spec["channels"],
                config=spec["config"],
                autostart=True,
                resources=spec["resources"],
                tap=False,
            )
            slot = int(created["slot"])
            if slot != expected_slot:
                raise RuntimeError(
                    f"{spec['name']} received slot {slot}, expected {expected_slot}"
                )
            print(f"  slot {slot:2d}: {spec['name']} -> {spec['app']}")

        h.set_active_instance(0)
        print("Resetting STM32 to start the new autostart layout ...")
        h.device_reset()
        return 0
    finally:
        h.close()


if __name__ == "__main__":
    raise SystemExit(main())
