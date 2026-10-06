from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .client import DaemonClient
from .device import LinHat
from .socket_protocol import DEFAULT_SOCKET_PATH


def parse_hex_bytes(value: str) -> bytes:
    cleaned = value.replace("0x", "").replace(":", "").replace(",", "").replace(" ", "")
    if len(cleaned) % 2:
        raise argparse.ArgumentTypeError("hex data must contain complete bytes")
    try:
        return bytes.fromhex(cleaned)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(str(exc)) from exc


def make_backend(args):
    if not args.direct and Path(args.socket).exists():
        return DaemonClient(args.socket)
    return LinHat(args.bus, args.address)


def main():
    p = argparse.ArgumentParser(prog="beiis-lin")
    p.add_argument("--bus", type=int, default=1)
    p.add_argument("--address", type=lambda x: int(x, 0), default=0x42)
    p.add_argument("--socket", default=DEFAULT_SOCKET_PATH)
    p.add_argument("--direct", action="store_true", help="bypass beiis-lind and access I2C directly")
    sp = p.add_subparsers(dest="cmd", required=True)

    sp.add_parser("info")
    sp.add_parser("ping")
    sp.add_parser("bootloader")
    sp.add_parser("mboot-info")
    sp.add_parser("mboot-reset")

    fl = sp.add_parser("flash")
    fl.add_argument("file")

    r = sp.add_parser("run")
    r.add_argument("file")

    e = sp.add_parser("exec")
    e.add_argument("code")

    u = sp.add_parser("put")
    u.add_argument("local")
    u.add_argument("remote")

    li = sp.add_parser("lin-init")
    li.add_argument("channel", type=int, choices=(1, 2))
    li.add_argument("baud", type=int)

    ls = sp.add_parser("lin-send")
    ls.add_argument("channel", type=int, choices=(1, 2))
    ls.add_argument("id", type=lambda x: int(x, 0))
    ls.add_argument("data", type=parse_hex_bytes)
    ls.add_argument("--classic", action="store_true")

    lr = sp.add_parser("lin-request")
    lr.add_argument("channel", type=int, choices=(1, 2))
    lr.add_argument("id", type=lambda x: int(x, 0))
    lr.add_argument("length", type=int, choices=range(0, 9))
    lr.add_argument("--classic", action="store_true")

    lss = sp.add_parser("lin-slave-set")
    lss.add_argument("channel", type=int, choices=(1, 2))
    lss.add_argument("id", type=lambda x: int(x, 0))
    lss.add_argument("data", type=parse_hex_bytes)
    lss.add_argument("--classic", action="store_true")

    lsc = sp.add_parser("lin-slave-clear")
    lsc.add_argument("channel", type=int, choices=(1, 2))

    a = p.parse_args()
    h = None
    try:
        h = make_backend(a)

        if a.cmd == "info":
            if isinstance(h, DaemonClient):
                print(h.info())
            else:
                print({"transport": "direct-i2c", "device": h.ping()})
        elif a.cmd == "ping":
            print(h.ping())
        elif a.cmd == "bootloader":
            h.bootloader()
        elif a.cmd == "mboot-info":
            print(h.mboot_info())
        elif a.cmd == "mboot-reset":
            h.mboot_reset()
        elif a.cmd == "flash":
            last = {}

            def progress(stage, done, total):
                pct = 100 if not total else int(done * 100 / total)
                prev = last.get(stage, -1)
                if pct == 100 or pct >= prev + 5 or prev < 0:
                    print(f"{stage}: {pct:3d}%")
                    last[stage] = pct

            result = h.flash_firmware(a.file, progress=progress)
            print(f"flash complete: {result['bytes']} bytes, sha256={result['sha256']}")
        elif a.cmd == "run":
            print(h.run_file(a.file), end="")
        elif a.cmd == "exec":
            print(h.exec(a.code), end="")
        elif a.cmd == "put":
            h.put(a.local, a.remote)
        elif a.cmd == "lin-init":
            h.lin_init(a.channel, a.baud)
        elif a.cmd == "lin-send":
            h.lin_send(a.channel, a.id, a.data, enhanced=not a.classic)
        elif a.cmd == "lin-request":
            data = h.lin_request(a.channel, a.id, a.length, enhanced=not a.classic)
            print(data.hex(" "))
        elif a.cmd == "lin-slave-set":
            h.lin_slave_set(a.channel, a.id, a.data, enhanced=not a.classic)
        elif a.cmd == "lin-slave-clear":
            h.lin_slave_clear(a.channel)
        return 0
    except (OSError, TimeoutError, RuntimeError, ValueError) as exc:
        print(f"beiis-lin: {exc}", file=sys.stderr)
        return 1
    finally:
        if h is not None:
            h.close()


if __name__ == "__main__":
    raise SystemExit(main())
