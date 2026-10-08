from __future__ import annotations

import argparse
import fcntl
import os
import signal
import socket
import threading
from pathlib import Path

from .device import LinHat
from .socket_protocol import (
    DEFAULT_SOCKET_PATH,
    MAX_PACKET,
    PROTOCOL_VERSION,
    decode_message,
    encode_message,
    error_message,
    event_message,
    reply_message,
)


class LinHatService:
    def __init__(self, device: LinHat):
        self.device = device
        self.lock = threading.RLock()

    @staticmethod
    def _bytes_arg(args: dict, name: str = "data") -> bytes:
        value = args.get(name, "")
        if not isinstance(value, str):
            raise ValueError(f"{name} must be a hexadecimal string")
        return bytes.fromhex(value)

    def dispatch(self, op: str, args: dict, progress=None):
        # GPIO IRQ waiting never touches I2C and must not hold the device lock.
        if op == "wait_irq":
            return {
                "event": self.device.wait_irq(float(args.get("timeout", 1.0))),
                "irq": self.device.irq_info(),
            }
        if op == "drain_irq":
            self.device.drain_irq()
            return {"ok": True}

        with self.lock:
            if op == "info":
                return {
                    "daemon_protocol": PROTOCOL_VERSION,
                    "device": self.device.ping(),
                    "irq": self.device.irq_info(),
                }
            if op == "ping":
                return self.device.ping()
            if op == "exec":
                return self.device.exec(str(args["source"]))
            if op == "enter_bootloader":
                self.device.bootloader()
                return {"mboot": True}
            if op == "mboot_info":
                return self.device.mboot_info()
            if op == "mboot_reset":
                self.device.mboot_reset()
                return {"reset": True}
            if op == "flash":
                return self.device.flash_firmware(str(args["path"]), progress=progress)

            if op == "data_info":
                return self.device.app_capabilities()
            if op == "active_instance":
                return {"active_instance": self.device.active_instance()}
            if op == "set_active_instance":
                self.device.set_active_instance(int(args["instance"]))
                return {"active_instance": self.device.active_instance()}
            if op == "data_send":
                self.device.data_send(int(args["channel"]), self._bytes_arg(args))
                return {"ok": True}
            if op == "data_recv":
                instance = args.get("instance")
                channel = args.get("channel")
                if instance is not None:
                    instance = int(instance)
                if channel is not None:
                    channel = int(channel)
                rx_instance, rx_channel, data = self.device.data_recv(
                    instance=instance, channel=channel, timeout=float(args.get("timeout", 2.0))
                )
                return {"instance": rx_instance, "channel": rx_channel, "data": data.hex()}
            if op == "runtime":
                return self.device.runtime_call(
                    str(args["op"]),
                    args.get("args") or {},
                    timeout=float(args.get("timeout", 2.0)),
                )

            if op == "lin_init":
                self.device.lin_init(int(args["channel"]), int(args["baud"]))
                return {"ok": True}
            if op == "lin_send":
                self.device.lin_send(
                    int(args["channel"]),
                    int(args["id"]),
                    self._bytes_arg(args),
                    bool(args.get("enhanced", True)),
                )
                return {"ok": True}
            if op == "lin_request":
                data = self.device.lin_request(
                    int(args["channel"]),
                    int(args["id"]),
                    int(args["length"]),
                    bool(args.get("enhanced", True)),
                )
                return {"data": data.hex()}
            if op == "lin_slave_set":
                self.device.lin_slave_set(
                    int(args["channel"]),
                    int(args["id"]),
                    self._bytes_arg(args),
                    bool(args.get("enhanced", True)),
                )
                return {"ok": True}
            if op == "lin_slave_clear":
                self.device.lin_slave_clear(int(args["channel"]))
                return {"ok": True}

            raise ValueError(f"unknown operation: {op}")


class LinHatDaemon:
    def __init__(
        self,
        bus: int = 1,
        address: int = 0x42,
        socket_path: str = DEFAULT_SOCKET_PATH,
        socket_mode: int = 0o660,
        lock_path: str | None = None,
        irq_gpio: int | None = 6,
        irq_chip: str | None = None,
    ):
        self.bus = bus
        self.address = address
        self.socket_path = Path(socket_path)
        self.socket_mode = socket_mode
        self.irq_gpio = irq_gpio
        self.irq_chip = irq_chip
        self.lock_path = Path(lock_path or f"/run/lock/beiis-lind-i2c{bus}.lock")
        self.stop_event = threading.Event()
        self.server = None
        self.device = None
        self.service = None
        self._lock_file = None
        self._threads: set[threading.Thread] = set()

    def _acquire_lock(self):
        self.lock_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock_file = self.lock_path.open("a+")
        try:
            fcntl.flock(self._lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise RuntimeError(f"I2C bus {self.bus} is already owned by another beiis-lind") from exc
        self._lock_file.seek(0)
        self._lock_file.truncate()
        self._lock_file.write(f"{os.getpid()}\n")
        self._lock_file.flush()

    def _prepare_socket(self):
        self.socket_path.parent.mkdir(parents=True, exist_ok=True)
        if self.socket_path.exists() or self.socket_path.is_symlink():
            self.socket_path.unlink()
        self.server = socket.socket(socket.AF_UNIX, socket.SOCK_SEQPACKET)
        self.server.bind(str(self.socket_path))
        os.chmod(self.socket_path, self.socket_mode)
        self.server.listen(16)
        self.server.settimeout(0.5)

    def _send(self, conn: socket.socket, message: dict):
        conn.sendall(encode_message(message))

    def _handle_client(self, conn: socket.socket):
        try:
            while not self.stop_event.is_set():
                data = conn.recv(MAX_PACKET)
                if not data:
                    return
                request_id = 0
                try:
                    request = decode_message(data)
                    request_id = int(request.get("id", 0))
                    if request.get("type") != "request":
                        raise ValueError("expected request packet")
                    op = str(request["op"])
                    args = request.get("args") or {}
                    if not isinstance(args, dict):
                        raise ValueError("request args must be an object")

                    def progress(stage: str, done: int, total: int):
                        try:
                            self._send(
                                conn,
                                event_message(
                                    request_id,
                                    "progress",
                                    {"stage": stage, "done": done, "total": total},
                                ),
                            )
                        except OSError:
                            # The update itself must continue if the client disappears.
                            pass

                    result = self.service.dispatch(op, args, progress=progress)
                    self._send(conn, reply_message(request_id, result))
                except Exception as exc:
                    try:
                        self._send(conn, error_message(request_id, exc))
                    except OSError:
                        return
        finally:
            conn.close()

    def serve_forever(self):
        self._acquire_lock()
        self.device = LinHat(
            self.bus,
            self.address,
            irq_gpio=self.irq_gpio,
            irq_chip=self.irq_chip,
        )
        if self.device.transport.irq is not None:
            self.device.prepare_host_irq()
        self.service = LinHatService(self.device)
        self._prepare_socket()

        try:
            while not self.stop_event.is_set():
                try:
                    conn, _ = self.server.accept()
                except socket.timeout:
                    continue
                thread = threading.Thread(target=self._handle_client, args=(conn,), daemon=True)
                self._threads.add(thread)
                thread.start()
                self._threads = {t for t in self._threads if t.is_alive()}
        finally:
            self.close()

    def close(self):
        self.stop_event.set()
        if self.server is not None:
            try:
                self.server.close()
            except OSError:
                pass
            self.server = None
        if self.device is not None:
            self.device.close()
            self.device = None
        try:
            if self.socket_path.exists() or self.socket_path.is_symlink():
                self.socket_path.unlink()
        except OSError:
            pass
        if self._lock_file is not None:
            try:
                fcntl.flock(self._lock_file.fileno(), fcntl.LOCK_UN)
                self._lock_file.close()
            finally:
                self._lock_file = None


def main():
    parser = argparse.ArgumentParser(prog="beiis-lind")
    parser.add_argument("--bus", type=int, default=1)
    parser.add_argument("--address", type=lambda x: int(x, 0), default=0x42)
    parser.add_argument("--socket", default=DEFAULT_SOCKET_PATH)
    parser.add_argument("--mode", type=lambda x: int(x, 8), default=0o660)
    parser.add_argument("--lock-file")
    parser.add_argument("--irq-gpio", type=int, default=6)
    parser.add_argument("--irq-chip")
    parser.add_argument("--no-irq", action="store_true")
    args = parser.parse_args()

    daemon = LinHatDaemon(
        bus=args.bus,
        address=args.address,
        socket_path=args.socket,
        socket_mode=args.mode,
        lock_path=args.lock_file,
        irq_gpio=None if args.no_irq else args.irq_gpio,
        irq_chip=args.irq_chip,
    )

    def stop(_signum, _frame):
        daemon.stop_event.set()
        if daemon.server is not None:
            try:
                daemon.server.close()
            except OSError:
                pass

    signal.signal(signal.SIGINT, stop)
    signal.signal(signal.SIGTERM, stop)

    try:
        daemon.serve_forever()
        return 0
    except KeyboardInterrupt:
        return 0
    except Exception as exc:
        print(f"beiis-lind: {exc}")
        return 1
    finally:
        daemon.close()


if __name__ == "__main__":
    raise SystemExit(main())
