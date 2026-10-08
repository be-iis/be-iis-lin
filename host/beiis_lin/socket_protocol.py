from __future__ import annotations

import json

PROTOCOL_VERSION = 1
DEFAULT_SOCKET_PATH = "/run/beiis/lin-hat.sock"
MAX_PACKET = 1024 * 1024


class ProtocolError(RuntimeError):
    pass


def encode_message(message: dict) -> bytes:
    message = dict(message)
    message.setdefault("v", PROTOCOL_VERSION)
    data = json.dumps(message, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    if len(data) > MAX_PACKET:
        raise ProtocolError(f"socket packet too large: {len(data)} bytes")
    return data


def decode_message(data: bytes) -> dict:
    if not data:
        raise ProtocolError("empty socket packet")
    try:
        message = json.loads(data.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ProtocolError(f"invalid socket packet: {exc}") from exc
    if not isinstance(message, dict):
        raise ProtocolError("socket packet must be a JSON object")
    if message.get("v") != PROTOCOL_VERSION:
        raise ProtocolError(f"unsupported protocol version: {message.get('v')!r}")
    return message


def request_message(request_id: int, op: str, args: dict | None = None) -> dict:
    return {
        "v": PROTOCOL_VERSION,
        "id": request_id,
        "type": "request",
        "op": op,
        "args": args or {},
    }


def reply_message(request_id: int, result=None) -> dict:
    return {
        "v": PROTOCOL_VERSION,
        "id": request_id,
        "type": "reply",
        "ok": True,
        "result": result,
    }


def error_message(request_id: int, exc: Exception) -> dict:
    return {
        "v": PROTOCOL_VERSION,
        "id": request_id,
        "type": "reply",
        "ok": False,
        "error": {
            "type": type(exc).__name__,
            "message": str(exc),
        },
    }


def event_message(request_id: int, event: str, data=None) -> dict:
    return {
        "v": PROTOCOL_VERSION,
        "id": request_id,
        "type": "event",
        "event": event,
        "data": data,
    }
