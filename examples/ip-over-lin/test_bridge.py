import unittest

from bridge import Reassembler, downlink_id, fragment_packet, uplink_id


def make_ipv4_packet(size=84):
    packet = bytearray(size)
    packet[0] = 0x45
    packet[2:4] = size.to_bytes(2, "big")
    packet[8] = 64
    packet[9] = 17
    packet[12:16] = bytes((10, 42, 1, 1))
    packet[16:20] = bytes((10, 42, 1, 2))
    for i in range(20, len(packet)):
        packet[i] = i & 0xFF
    return bytes(packet)


class IpBridgeProtocolTest(unittest.TestCase):
    def test_fragment_round_trip(self):
        packet = make_ipv4_packet()
        frames = fragment_packet(packet, 7)
        self.assertEqual(len(frames), 14)

        reassembler = Reassembler()
        result = None
        for frame in frames:
            result = reassembler.feed(frame)

        self.assertEqual(result, packet)

    def test_bidirectional_lin_ids_are_distinct(self):
        self.assertEqual(downlink_id(2), 0x02)
        self.assertEqual(uplink_id(2), 0x22)
        self.assertNotEqual(downlink_id(2), uplink_id(2))

    def test_node_range(self):
        for node in (2, 3, 15, 31):
            self.assertLessEqual(uplink_id(node), 0x3F)

        with self.assertRaises(ValueError):
            downlink_id(1)
        with self.assertRaises(ValueError):
            downlink_id(32)

    def test_reassembler_rejects_wrong_sequence(self):
        packet = make_ipv4_packet()
        frames = fragment_packet(packet, 3)
        broken = list(frames)
        bad = bytearray(broken[1])
        bad[0] = (bad[0] & 0xC0) | 4
        broken[1] = bytes(bad)

        reassembler = Reassembler()
        result = None
        for frame in broken:
            result = reassembler.feed(frame)

        self.assertIsNone(result)


if __name__ == "__main__":
    unittest.main()
