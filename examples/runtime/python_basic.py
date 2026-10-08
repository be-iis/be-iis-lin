#!/usr/bin/env python3
from __future__ import annotations

import argparse

from beiis_lin.client import DaemonClient


MASTER_TX = 0
MASTER_RX = 1
SLAVE_TX = 3
SLAVE_RX = 4
LOG_TX = 6
LOG_RX = 7
CHANNEL = 0


def parse_id(value: str) -> int:
    result = int(value, 0)
    if not 0 <= result <= 0x3F:
        raise argparse.ArgumentTypeError("LIN ID must be 0..0x3f")
    return result


def parse_hex(value: str) -> bytes:
    cleaned = value.replace(":", "").replace(" ", "")
    try:
        data = bytes.fromhex(cleaned)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(str(exc)) from exc
    if len(data) > 8:
        raise argparse.ArgumentTypeError("LIN payload must be 0..8 bytes")
    return data


def rpc(c: DaemonClient, tx_slot: int, rx_slot: int, request: bytes) -> tuple[int, bytes]:
    c.set_active_instance(tx_slot)
    c.data_send(CHANNEL, request)
    instance, channel, reply = c.data_recv(
        instance=rx_slot,
        channel=CHANNEL,
        timeout=2.0,
    )
    if instance != rx_slot or channel != CHANNEL or len(reply) < 2:
        raise RuntimeError(f"invalid runtime reply: {instance=} {channel=} {reply=!r}")
    if reply[0] != request[0]:
        raise RuntimeError(f"operation mismatch: request={request.hex()} reply={reply.hex()}")
    return reply[1], reply[2:]


def require_ok(op: int, status: int, payload: bytes) -> bytes:
    if status != 0:
        text = payload.decode("utf-8", "replace")
        raise RuntimeError(f"operation 0x{op:02x} failed status={status}: {text}")
    return payload


def main() -> int:
    p = argparse.ArgumentParser(description="BE-IIS runtime LIN socket example")
    p.add_argument("--socket", default="/run/beiis/lin-hat.sock")
    sp = p.add_subparsers(dest="cmd", required=True)

    sp.add_parser("master-ping")

    s = sp.add_parser("master-send")
    s.add_argument("id", type=parse_id)
    s.add_argument("data", type=parse_hex)
    s.add_argument("--classic", action="store_true")

    r = sp.add_parser("master-request")
    r.add_argument("id", type=parse_id)
    r.add_argument("length", type=int, choices=range(0, 9))
    r.add_argument("--classic", action="store_true")

    ss = sp.add_parser("slave-set")
    ss.add_argument("id", type=parse_id)
    ss.add_argument("data", type=parse_hex)
    ss.add_argument("--classic", action="store_true")

    sp.add_parser("slave-clear")

    sr = sp.add_parser("slave-rx-set")
    sr.add_argument("id", type=parse_id)
    sr.add_argument("length", type=int, choices=range(0, 9))
    sr.add_argument("--classic", action="store_true")

    sp.add_parser("slave-rx-recv")
    sp.add_parser("logging-ping")
    sp.add_parser("logging-status")

    a = p.parse_args()
    c = DaemonClient(a.socket)
    try:
        if a.cmd == "master-ping":
            status, payload = rpc(c, MASTER_TX, MASTER_RX, b"\x00")
            require_ok(0x00, status, payload)
            print("master native: OK")

        elif a.cmd == "master-send":
            flags = 0 if a.classic else 1
            req = bytes((0x02, a.id, flags, len(a.data))) + a.data
            status, payload = rpc(c, MASTER_TX, MASTER_RX, req)
            require_ok(0x02, status, payload)
            print("sent")

        elif a.cmd == "master-request":
            flags = 0 if a.classic else 1
            req = bytes((0x03, a.id, flags, a.length))
            status, payload = rpc(c, MASTER_TX, MASTER_RX, req)
            payload = require_ok(0x03, status, payload)
            if not payload:
                raise RuntimeError("missing response length")
            length = payload[0]
            data = payload[1:]
            if len(data) != length:
                raise RuntimeError("response length mismatch")
            print(data.hex(" "))

        elif a.cmd == "slave-set":
            flags = 0 if a.classic else 1
            req = bytes((0x04, a.id, flags, len(a.data))) + a.data
            status, payload = rpc(c, SLAVE_TX, SLAVE_RX, req)
            require_ok(0x04, status, payload)
            print("slave response configured")

        elif a.cmd == "slave-clear":
            status, payload = rpc(c, SLAVE_TX, SLAVE_RX, b"\x05")
            require_ok(0x05, status, payload)
            print("slave response cleared")

        elif a.cmd == "slave-rx-set":
            flags = 0 if a.classic else 1
            req = bytes((0x08, a.id, flags, a.length))
            status, payload = rpc(c, SLAVE_TX, SLAVE_RX, req)
            require_ok(0x08, status, payload)
            print("slave receive configured")

        elif a.cmd == "slave-rx-recv":
            status, payload = rpc(c, SLAVE_TX, SLAVE_RX, b"\x09")
            payload = require_ok(0x09, status, payload)
            if payload == b"\x00":
                print("no frame")
            elif len(payload) >= 2 and payload[0] == 1:
                length = payload[1]
                data = payload[2:]
                if len(data) != length:
                    raise RuntimeError("slave receive length mismatch")
                print(data.hex(" "))
            else:
                raise RuntimeError(f"invalid slave receive reply: {payload.hex()}")

        elif a.cmd == "logging-ping":
            status, payload = rpc(c, LOG_TX, LOG_RX, b"\x00")
            require_ok(0x00, status, payload)
            print("logging native: OK")

        elif a.cmd == "logging-status":
            status, payload = rpc(c, LOG_TX, LOG_RX, b"\x01")
            print(f"status={status} message={payload.decode('utf-8', 'replace')}")

        return 0
    finally:
        c.close()


if __name__ == "__main__":
    raise SystemExit(main())
