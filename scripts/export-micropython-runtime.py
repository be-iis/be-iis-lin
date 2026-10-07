#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

from beiis_lin.device import LinHat


def read_remote_file(hat: LinHat, path: str) -> bytes:
    code = (
        "import binascii\n"
        f"_p={path!r}\n"
        "_f=open(_p,'rb')\n"
        "_d=_f.read()\n"
        "_f.close()\n"
        "print(binascii.hexlify(_d).decode())\n"
        "del _d,_f,_p\n"
    )
    out = hat.exec(code).strip()
    return bytes.fromhex(out)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Export deployed BE-IIS MicroPython runtime apps from the STM32"
    )
    parser.add_argument("--bus", type=int, default=1)
    parser.add_argument("--address", type=lambda value: int(value, 0), default=0x42)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("stm32/micropython/apps/deployed"),
    )
    args = parser.parse_args()

    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)

    hat = LinHat(args.bus, args.address)
    stopped = False
    try:
        info = hat.runtime_call("info", timeout=2.0)
        apps = list(info.get("apps") or [])
        print("runtime instances:")
        for item in info.get("instances") or []:
            print(
                "  slot={slot:2d} name={name} app={app} state={state}".format(
                    slot=int(item.get("slot", -1)),
                    name=item.get("name", "?"),
                    app=item.get("app", "?"),
                    state=item.get("state", "?"),
                )
            )

        result = hat.runtime_stop()
        if result is not True:
            raise RuntimeError(f"runtime_stop returned {result!r}")
        stopped = True

        config = read_remote_file(hat, "/flash/beiis/instances.json")
        (output / "instances.json").write_bytes(config)

        exported = []
        for app in apps:
            if not isinstance(app, str) or not app:
                raise RuntimeError(f"invalid app name returned by runtime: {app!r}")
            data = read_remote_file(hat, f"/flash/beiis/apps/{app}.py")
            path = output / f"{app}.py"
            path.write_bytes(data)
            exported.append(path.name)

        manifest = {
            "source": "STM32 /flash/beiis",
            "apps": apps,
            "files": ["instances.json", *exported],
        }
        (output / "EXPORT.json").write_text(
            json.dumps(manifest, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

        print(f"exported {len(apps)} app(s) to {output}")
        for name in manifest["files"]:
            print(f"  {name}")
        return 0
    finally:
        try:
            if stopped:
                hat.device_reset()
        finally:
            hat.close()


if __name__ == "__main__":
    raise SystemExit(main())
