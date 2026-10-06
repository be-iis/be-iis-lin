from __future__ import annotations

import os
import socket
from pathlib import Path

from .socket_protocol import DEFAULT_SOCKET_PATH, MAX_PACKET, decode_message, encode_message, request_message


class DaemonError(RuntimeError):
    pass


class DaemonClient:
    def __init__(self, socket_path: str = DEFAULT_SOCKET_PATH):
        self.socket_path = socket_path
        self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_SEQPACKET)
        self.sock.connect(socket_path)
        self._next_id = 1

    def close(self):
        self.sock.close()

    def _call(self, op: str, args: dict | None = None, progress=None):
        request_id = self._next_id
        self._next_id += 1
        self.sock.sendall(encode_message(request_message(request_id, op, args)))

        while True:
            data = self.sock.recv(MAX_PACKET)
            message = decode_message(data)
            if message.get("id") != request_id:
                continue
            if message.get("type") == "event":
                if progress is not None and message.get("event") == "progress":
                    p = message.get("data") or {}
                    progress(p.get("stage", ""), int(p.get("done", 0)), int(p.get("total", 0)))
                continue
            if message.get("type") != "reply":
                continue
            if message.get("ok"):
                return message.get("result")
            error = message.get("error") or {}
            raise DaemonError(f"{error.get('type', 'Error')}: {error.get('message', '')}")

    def info(self):
        return self._call("info")

    def ping(self):
        return self._call("ping")

    def exec(self, source: str) -> str:
        return self._call("exec", {"source": source})

    def bootloader(self):
        return self._call("enter_bootloader")

    def mboot_info(self):
        return self._call("mboot_info")

    def mboot_reset(self):
        return self._call("mboot_reset")

    def flash_firmware(self, path: str | Path, progress=None):
        return self._call(
            "flash",
            {"path": str(Path(path).expanduser().resolve())},
            progress=progress,
        )

    def run_file(self, path: str | Path) -> str:
        return self.exec(Path(path).read_text(encoding="utf-8"))

    def put(self, local: str | Path, remote: str):
        data = Path(local).read_bytes()
        code = (
            "import binascii\n"
            f"_d=binascii.unhexlify('{data.hex()}')\n"
            f"open({remote!r},'wb').write(_d)\n"
            "del _d\n"
        )
        return self.exec(code)

    def lin_init(self, channel: int, baud: int):
        return self._call("lin_init", {"channel": channel, "baud": baud})

    def lin_send(self, channel: int, frame_id: int, data: bytes, enhanced: bool = True):
        return self._call(
            "lin_send",
            {
                "channel": channel,
                "id": frame_id,
                "data": data.hex(),
                "enhanced": enhanced,
            },
        )

    def lin_request(self, channel: int, frame_id: int, length: int, enhanced: bool = True) -> bytes:
        result = self._call(
            "lin_request",
            {
                "channel": channel,
                "id": frame_id,
                "length": length,
                "enhanced": enhanced,
            },
        )
        return bytes.fromhex(result["data"])

    def lin_slave_set(self, channel: int, frame_id: int, data: bytes, enhanced: bool = True):
        return self._call(
            "lin_slave_set",
            {
                "channel": channel,
                "id": frame_id,
                "data": data.hex(),
                "enhanced": enhanced,
            },
        )

    def lin_slave_clear(self, channel: int):
        return self._call("lin_slave_clear", {"channel": channel})
