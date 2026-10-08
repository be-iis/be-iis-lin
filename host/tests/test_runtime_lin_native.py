from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
APP_PATH = ROOT / "stm32" / "micropython" / "apps" / "lin_native.py"


def load_app():
    spec = importlib.util.spec_from_file_location("beiis_test_lin_native", APP_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class FakeLin:
    def __init__(self):
        self.calls = []
        self.request_data = b"\x11\x22\x33\x44"
        self.led_mask = 0

    def init(self, channel, baud):
        self.calls.append(("init", channel, baud))

    def send(self, channel, frame_id, data, enhanced):
        self.calls.append(("send", channel, frame_id, bytes(data), enhanced))

    def request(self, channel, frame_id, length, enhanced):
        self.calls.append(("request", channel, frame_id, length, enhanced))
        return self.request_data[:length]

    def slave_set(self, channel, frame_id, data, enhanced):
        self.calls.append(("slave_set", channel, frame_id, bytes(data), enhanced))

    def slave_clear(self, channel):
        self.calls.append(("slave_clear", channel))

    def leds(self, *args):
        if args:
            self.led_mask = int(args[0])
        self.calls.append(("leds", self.led_mask))
        return self.led_mask


class LinNativeProtocolTest(unittest.TestCase):
    def setUp(self):
        self.app = load_app()
        self.lin = FakeLin()

    def test_ping(self):
        self.assertEqual(
            self.app.handle_request(self.lin, 1, b"\x00"),
            b"\x00\x00",
        )

    def test_init(self):
        request = bytes((self.app.OP_INIT,)) + (19200).to_bytes(4, "little")
        self.assertEqual(
            self.app.handle_request(self.lin, 2, request),
            bytes((self.app.OP_INIT, self.app.STATUS_OK)),
        )
        self.assertEqual(self.lin.calls[-1], ("init", 2, 19200))

    def test_send(self):
        request = bytes((self.app.OP_SEND, 0x12, 1, 4, 1, 2, 3, 4))
        reply = self.app.handle_request(self.lin, 1, request)
        self.assertEqual(reply, bytes((self.app.OP_SEND, self.app.STATUS_OK)))
        self.assertEqual(
            self.lin.calls[-1],
            ("send", 1, 0x12, b"\x01\x02\x03\x04", True),
        )

    def test_request(self):
        request = bytes((self.app.OP_REQUEST, 0x22, 0, 4))
        reply = self.app.handle_request(self.lin, 1, request)
        self.assertEqual(
            reply,
            bytes((self.app.OP_REQUEST, self.app.STATUS_OK, 4))
            + b"\x11\x22\x33\x44",
        )
        self.assertEqual(
            self.lin.calls[-1],
            ("request", 1, 0x22, 4, False),
        )

    def test_slave_set_and_clear(self):
        request = bytes((self.app.OP_SLAVE_SET, 0x22, 1, 3, 0xAA, 0xBB, 0xCC))
        reply = self.app.handle_request(self.lin, 2, request)
        self.assertEqual(
            reply,
            bytes((self.app.OP_SLAVE_SET, self.app.STATUS_OK)),
        )
        self.assertEqual(
            self.lin.calls[-1],
            ("slave_set", 2, 0x22, b"\xaa\xbb\xcc", True),
        )

        reply = self.app.handle_request(
            self.lin, 2, bytes((self.app.OP_SLAVE_CLEAR,))
        )
        self.assertEqual(
            reply,
            bytes((self.app.OP_SLAVE_CLEAR, self.app.STATUS_OK)),
        )
        self.assertEqual(self.lin.calls[-1], ("slave_clear", 2))

    def test_leds(self):
        reply = self.app.handle_request(
            self.lin, 1, bytes((self.app.OP_LEDS_SET, 0x55))
        )
        self.assertEqual(
            reply,
            bytes((self.app.OP_LEDS_SET, self.app.STATUS_OK, 0x55)),
        )

        reply = self.app.handle_request(
            self.lin, 1, bytes((self.app.OP_LEDS_GET,))
        )
        self.assertEqual(
            reply,
            bytes((self.app.OP_LEDS_GET, self.app.STATUS_OK, 0x55)),
        )

    def test_bad_length(self):
        reply = self.app.handle_request(
            self.lin,
            1,
            bytes((self.app.OP_SEND, 0x12, 1, 8, 0x01)),
        )
        self.assertEqual(reply[0], self.app.OP_SEND)
        self.assertEqual(reply[1], self.app.STATUS_BAD_REQUEST)


if __name__ == "__main__":
    unittest.main()
