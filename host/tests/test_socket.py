import unittest

from beiis_lin.daemon import LinHatService
from beiis_lin.socket_protocol import (
    decode_message,
    encode_message,
    error_message,
    event_message,
    reply_message,
    request_message,
)


class FakeDevice:
    def __init__(self):
        self.calls = []

    def ping(self):
        return {"protocol_version": 1, "status": 0x83}

    def exec(self, source):
        self.calls.append(("exec", source))
        return "ok\n"

    def bootloader(self):
        self.calls.append(("bootloader",))

    def mboot_info(self):
        return {"mcu": "STM32G0B0KET6", "board": "BE-IIS LIN HAT"}

    def mboot_reset(self):
        self.calls.append(("mboot_reset",))

    def flash_firmware(self, path, progress=None):
        if progress:
            progress("write", 50, 100)
        self.calls.append(("flash", path))
        return {"bytes": 100, "sha256": "00"}

    def lin_init(self, channel, baud):
        self.calls.append(("lin_init", channel, baud))

    def lin_send(self, channel, frame_id, data, enhanced=True):
        self.calls.append(("lin_send", channel, frame_id, data, enhanced))

    def lin_request(self, channel, frame_id, length, enhanced=True):
        self.calls.append(("lin_request", channel, frame_id, length, enhanced))
        return b"\x11\x22"

    def lin_slave_set(self, channel, frame_id, data, enhanced=True):
        self.calls.append(("lin_slave_set", channel, frame_id, data, enhanced))

    def lin_slave_clear(self, channel):
        self.calls.append(("lin_slave_clear", channel))


class SocketProtocolTest(unittest.TestCase):
    def test_request_round_trip(self):
        original = request_message(7, "lin_request", {"channel": 1})
        self.assertEqual(decode_message(encode_message(original)), original)

    def test_reply_event_error(self):
        self.assertTrue(reply_message(1, {"a": 2})["ok"])
        self.assertEqual(event_message(1, "progress", {})["type"], "event")
        self.assertFalse(error_message(1, RuntimeError("x"))["ok"])


class ServiceDispatchTest(unittest.TestCase):
    def setUp(self):
        self.device = FakeDevice()
        self.service = LinHatService(self.device)

    def test_lin_request(self):
        result = self.service.dispatch(
            "lin_request",
            {"channel": 1, "id": 0x22, "length": 2, "enhanced": False},
        )
        self.assertEqual(result, {"data": "1122"})
        self.assertEqual(self.device.calls[-1], ("lin_request", 1, 0x22, 2, False))

    def test_lin_send_hex_decode(self):
        self.service.dispatch(
            "lin_send",
            {"channel": 2, "id": 0x12, "data": "01020304", "enhanced": True},
        )
        self.assertEqual(
            self.device.calls[-1],
            ("lin_send", 2, 0x12, b"\x01\x02\x03\x04", True),
        )

    def test_flash_progress(self):
        events = []
        result = self.service.dispatch(
            "flash",
            {"path": "/tmp/firmware.bin"},
            progress=lambda stage, done, total: events.append((stage, done, total)),
        )
        self.assertEqual(result["bytes"], 100)
        self.assertEqual(events, [("write", 50, 100)])

    def test_unknown_operation(self):
        with self.assertRaises(ValueError):
            self.service.dispatch("does_not_exist", {})


if __name__ == "__main__":
    unittest.main()
