import unittest

from beiis_lin.ip_bridge import Reassembler, fragment_packet, icmp_echo_reply, internet_checksum


def make_echo_request():
    packet = bytearray(84)
    packet[0] = 0x45
    packet[2:4] = (84).to_bytes(2, "big")
    packet[4:6] = (0x1234).to_bytes(2, "big")
    packet[8] = 64
    packet[9] = 1
    packet[12:16] = bytes((10, 42, 1, 1))
    packet[16:20] = bytes((10, 42, 1, 2))
    packet[20] = 8
    packet[21] = 0
    packet[24:26] = (0x4321).to_bytes(2, "big")
    packet[26:28] = (1).to_bytes(2, "big")
    for i in range(28, len(packet)):
        packet[i] = i & 0xFF
    packet[22:24] = internet_checksum(packet[20:]).to_bytes(2, "big")
    packet[10:12] = internet_checksum(packet[:20]).to_bytes(2, "big")
    return bytes(packet)


class IpBridgeProtocolTest(unittest.TestCase):
    def test_fragment_round_trip(self):
        packet = make_echo_request()
        frames = fragment_packet(packet, 7)
        self.assertEqual(len(frames), 14)
        reassembler = Reassembler()
        result = None
        for frame in frames:
            result = reassembler.feed(frame)
        self.assertEqual(result, packet)

    def test_icmp_echo_reply(self):
        request = make_echo_request()
        reply = icmp_echo_reply(request, 2)
        self.assertIsNotNone(reply)
        self.assertEqual(reply[12:16], request[16:20])
        self.assertEqual(reply[16:20], request[12:16])
        self.assertEqual(reply[20], 0)
        self.assertEqual(internet_checksum(reply[:20]), 0)
        self.assertEqual(internet_checksum(reply[20:]), 0)

    def test_wrong_node_not_answered(self):
        self.assertIsNone(icmp_echo_reply(make_echo_request(), 3))


if __name__ == "__main__":
    unittest.main()
