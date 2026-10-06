import hashlib
import struct
import tempfile
import unittest

from beiis_lin.mboot import APP_START, FLASH_PAGE_SIZE, MbootClient


class SimMboot(MbootClient):
    def __init__(self):
        self.mem = bytearray(b"\xff" * FLASH_PAGE_SIZE)
        self.write_address = APP_START
        self.marked = False

    def page_erase(self, address: int):
        if address != APP_START:
            raise AssertionError(f"unexpected erase address 0x{address:08x}")
        self.mem[:] = b"\xff" * len(self.mem)

    def set_write_address(self, address: int):
        self.write_address = address

    def write(self, data: bytes):
        off = self.write_address - APP_START
        self.mem[off : off + len(data)] = data
        self.write_address += len(data)

    def calculate_hash(self, address: int, length: int) -> bytes:
        if address != APP_START:
            raise AssertionError(f"unexpected hash address 0x{address:08x}")
        return hashlib.sha256(self.mem[:length]).digest()

    def mark_valid(self, vector: bytes):
        if self.mem[:8] != b"\xff" * 8:
            raise AssertionError("application vector was not left erased before MARKVALID")
        if len(vector) != 8:
            raise AssertionError("MARKVALID vector length")
        self.mem[:8] = vector
        self.marked = True


class MbootFlashTest(unittest.TestCase):
    def test_full_flash_validity_and_hash_flow(self):
        m = SimMboot()
        image = struct.pack("<I", 0x2001E000) + b"BE-IIS firmware!"
        with tempfile.NamedTemporaryFile() as f:
            f.write(image)
            f.flush()
            result = m.flash_application(f.name)

        self.assertTrue(m.marked)
        self.assertEqual(m.mem[:len(image)], image)
        self.assertEqual(result["sha256"], hashlib.sha256(image).hexdigest())


if __name__ == "__main__":
    unittest.main()
