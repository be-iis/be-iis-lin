from __future__ import annotations

import hashlib
import struct
import time
from pathlib import Path

I2C_CMD_ECHO = 0x01
I2C_CMD_GETID = 0x02
I2C_CMD_RESET = 0x04
I2C_CMD_GETLAYOUT = 0x06
I2C_CMD_PAGEERASE = 0x08
I2C_CMD_SETRDADDR = 0x09
I2C_CMD_SETWRADDR = 0x0A
I2C_CMD_READ = 0x0B
I2C_CMD_WRITE = 0x0C
I2C_CMD_CALCHASH = 0x0E
I2C_CMD_MARKVALID = 0x0F

APP_START = 0x08008000
APP_END = 0x08058000
FLASH_PAGE_SIZE = 2048
WRITE_CHUNK = 128


class MbootError(RuntimeError):
    pass


class MbootClient:
    def __init__(self, transport):
        self.t = transport

    @staticmethod
    def _signed_u8(value: int) -> int:
        return value - 256 if value & 0x80 else value

    def _write_when_ready(self, data: bytes, timeout: float = 2.0):
        deadline = time.monotonic() + timeout
        last_exc = None
        while time.monotonic() < deadline:
            try:
                self.t.raw_write(data)
                return
            except OSError as exc:
                last_exc = exc
                time.sleep(0.01)
        raise TimeoutError("mboot did not accept I2C command") from last_exc

    def _read_when_ready(self, n: int, timeout: float = 2.0) -> bytes:
        deadline = time.monotonic() + timeout
        last_exc = None
        while time.monotonic() < deadline:
            try:
                return self.t.raw_read(n)
            except OSError as exc:
                last_exc = exc
                time.sleep(0.01)
        raise TimeoutError("mboot did not become ready after command") from last_exc

    def command(self, cmd: int, payload: bytes = b"", *, timeout: float = 2.0) -> tuple[int, bytes]:
        if len(payload) > 128:
            raise ValueError("mboot I2C payload is limited to 128 bytes")
        self._write_when_ready(bytes([cmd]) + payload, timeout=timeout)
        arg = self._read_when_ready(1, timeout=timeout)[0]
        signed = self._signed_u8(arg)
        if signed < 0:
            raise MbootError(f"mboot command 0x{cmd:02x} failed: {signed}")
        data = self._read_when_ready(arg, timeout=timeout) if arg else b""
        return arg, data

    def echo(self):
        arg, data = self.command(I2C_CMD_ECHO)
        if arg != 1 or data != b"\x01":
            raise MbootError(f"unexpected mboot ECHO response: arg={arg}, data={data!r}")

    def get_id(self) -> bytes:
        arg, data = self.command(I2C_CMD_GETID)
        if len(data) != arg:
            raise MbootError("short GETID response")
        return data

    def get_layout(self) -> str:
        _, data = self.command(I2C_CMD_GETLAYOUT)
        return data.rstrip(b"\x00").decode("ascii", "replace")

    def set_read_address(self, address: int):
        arg, _ = self.command(I2C_CMD_SETRDADDR, struct.pack("<I", address))
        if arg != 0:
            raise MbootError(f"SETRDADDR returned {arg}")

    def set_write_address(self, address: int):
        arg, _ = self.command(I2C_CMD_SETWRADDR, struct.pack("<I", address))
        if arg != 0:
            raise MbootError(f"SETWRADDR returned {arg}")

    def page_erase(self, address: int):
        arg, _ = self.command(I2C_CMD_PAGEERASE, struct.pack("<I", address), timeout=3.0)
        if arg != 0:
            raise MbootError(f"PAGEERASE returned {arg}")

    def write(self, data: bytes):
        if not data or len(data) > WRITE_CHUNK or len(data) % 8:
            raise ValueError("mboot write must be 8..128 bytes and 8-byte aligned")
        arg, _ = self.command(I2C_CMD_WRITE, data, timeout=2.0)
        if arg != 0:
            raise MbootError(f"WRITE returned {arg}")

    def calculate_hash(self, address: int, length: int) -> bytes:
        self.set_read_address(address)
        arg, data = self.command(I2C_CMD_CALCHASH, struct.pack("<I", length), timeout=3.0)
        if arg != 32 or len(data) != 32:
            raise MbootError(f"CALCHASH returned {arg} bytes")
        return data

    def mark_valid(self, vector: bytes):
        if len(vector) != 8:
            raise ValueError("MARKVALID requires the original 8-byte application vector")
        arg, _ = self.command(I2C_CMD_MARKVALID, vector, timeout=2.0)
        if arg != 0:
            raise MbootError(f"MARKVALID returned {arg}")

    def reset(self):
        # RESET intentionally tears down mboot, so don't wait for a reply.
        self._write_when_ready(bytes([I2C_CMD_RESET]), timeout=1.0)

    @staticmethod
    def parse_id(data: bytes) -> dict:
        if len(data) < 14:
            return {"uid": data.hex(), "mcu": "", "board": ""}
        uid = data[:12].hex()
        rest = data[12:]
        mcu_raw, sep, board_raw = rest.partition(b"\x00")
        return {
            "uid": uid,
            "mcu": mcu_raw.decode("ascii", "replace"),
            "board": board_raw.decode("ascii", "replace") if sep else "",
        }

    def flash_application(self, path: str | Path, progress=None):
        image = Path(path).read_bytes()
        if len(image) < 8:
            raise ValueError("firmware image is too small")
        if len(image) > APP_END - APP_START:
            raise ValueError(
                f"firmware image is {len(image)} bytes; application region is {APP_END - APP_START} bytes"
            )

        # mboot uses the low two bits of the initial MSP as the update-validity marker.
        first_word = struct.unpack_from("<I", image, 0)[0]
        if first_word & 0x3:
            raise ValueError("firmware initial MSP is not compatible with mboot validity bits")

        def report(stage: str, done: int = 0, total: int = 0):
            if progress is not None:
                progress(stage, done, total)

        erase_end = (APP_START + len(image) + FLASH_PAGE_SIZE - 1) & ~(FLASH_PAGE_SIZE - 1)
        pages = list(range(APP_START, erase_end, FLASH_PAGE_SIZE))

        report("erase", 0, len(pages))
        for i, address in enumerate(pages, 1):
            self.page_erase(address)
            report("erase", i, len(pages))

        # STM32G0 flash doublewords include ECC and cannot be programmed twice.
        # Leave the first 8-byte vector doubleword erased during the update and
        # write the remaining image starting at APP_START+8.
        self.set_write_address(APP_START + 8)
        body = image[8:]
        padded_len = (len(body) + 7) & ~7
        padded = body + b"\xff" * (padded_len - len(body))
        report("write", 0, len(image))
        written = 8
        for offset in range(0, len(padded), WRITE_CHUNK):
            chunk = padded[offset : offset + WRITE_CHUNK]
            self.write(chunk)
            written = min(8 + offset + len(chunk), len(image))
            report("write", written, len(image))

        # Before MARKVALID the vector doubleword is still erased.
        invalid_image = bytearray(image)
        invalid_image[:8] = b"\xff" * 8
        expected_invalid = hashlib.sha256(invalid_image).digest()
        report("verify-invalid", 0, len(image))
        actual_invalid = self.calculate_hash(APP_START, len(image))
        if actual_invalid != expected_invalid:
            raise MbootError(
                "SHA-256 mismatch before MARKVALID: "
                f"device={actual_invalid.hex()} expected={expected_invalid.hex()}"
            )
        report("verify-invalid", len(image), len(image))

        self.mark_valid(image[:8])

        expected = hashlib.sha256(image).digest()
        report("verify-final", 0, len(image))
        actual = self.calculate_hash(APP_START, len(image))
        if actual != expected:
            raise MbootError(
                "SHA-256 mismatch after MARKVALID: "
                f"device={actual.hex()} expected={expected.hex()}"
            )
        report("verify-final", len(image), len(image))

        return {
            "bytes": len(image),
            "pages": len(pages),
            "sha256": expected.hex(),
        }
