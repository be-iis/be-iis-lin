from __future__ import annotations

import argparse
import fcntl
import ipaddress
import os
import selectors
import struct
import subprocess
import time
from collections import deque

from beiis_lin.client import DaemonClient, DaemonError
from beiis_lin.socket_protocol import DEFAULT_SOCKET_PATH


TUNSETIFF = 0x400454CA
IFF_TUN = 0x0001
IFF_NO_PI = 0x1000

FRAME_SIZE = 8
HEADER_SIZE = 2
PAYLOAD_SIZE = FRAME_SIZE - HEADER_SIZE
SEQ_MASK = 0x3F
FLAG_END = 0x40
FLAG_START = 0x80


def fragment_packet(packet: bytes, sequence: int) -> list[bytes]:
    sequence &= SEQ_MASK
    if sequence == 0:
        sequence = 1

    frames: list[bytes] = []
    offset = 0
    index = 0

    while offset < len(packet):
        chunk = packet[offset : offset + PAYLOAD_SIZE]
        control = sequence
        if offset == 0:
            control |= FLAG_START

        offset += len(chunk)
        if offset >= len(packet):
            control |= FLAG_END

        frame = bytearray(FRAME_SIZE)
        frame[0] = control
        frame[1] = index & 0xFF
        frame[2 : 2 + len(chunk)] = chunk
        frames.append(bytes(frame))
        index += 1

    return frames


class Reassembler:
    def __init__(self) -> None:
        self.reset()

    def reset(self) -> None:
        self.sequence = 0
        self.next_index = 0
        self.total_length = 0
        self.data = bytearray()

    def feed(self, frame: bytes) -> bytes | None:
        if len(frame) != FRAME_SIZE:
            self.reset()
            return None

        control = frame[0]
        sequence = control & SEQ_MASK
        index = frame[1]
        start = bool(control & FLAG_START)
        end = bool(control & FLAG_END)

        if sequence == 0:
            self.reset()
            return None

        if start:
            if index != 0:
                self.reset()
                return None
            self.sequence = sequence
            self.next_index = 0
            self.total_length = 0
            self.data = bytearray()

        if sequence != self.sequence or index != self.next_index:
            self.reset()
            return None

        self.data.extend(frame[2:])
        self.next_index += 1

        if self.total_length == 0 and len(self.data) >= 4:
            if (self.data[0] >> 4) != 4:
                self.reset()
                return None
            self.total_length = (self.data[2] << 8) | self.data[3]
            if self.total_length < 20 or self.total_length > 1500:
                self.reset()
                return None

        if not end:
            return None

        if not self.total_length or len(self.data) < self.total_length:
            self.reset()
            return None

        packet = bytes(self.data[: self.total_length])
        self.reset()
        return packet


def internet_checksum(data: bytes) -> int:
    total = 0
    length = len(data)
    index = 0

    while index + 1 < length:
        total += (data[index] << 8) | data[index + 1]
        total = (total & 0xFFFF) + (total >> 16)
        index += 2

    if index < length:
        total += data[index] << 8
        total = (total & 0xFFFF) + (total >> 16)

    while total >> 16:
        total = (total & 0xFFFF) + (total >> 16)

    return (~total) & 0xFFFF


def icmp_echo_reply(packet: bytes, node: int) -> bytes | None:
    if len(packet) < 28 or (packet[0] >> 4) != 4:
        return None

    ihl = (packet[0] & 0x0F) * 4
    if ihl < 20 or len(packet) < ihl + 8:
        return None

    total_length = (packet[2] << 8) | packet[3]
    if total_length < ihl + 8 or total_length > len(packet):
        return None

    if packet[9] != 1:
        return None

    if packet[19] != node:
        return None

    if packet[ihl] != 8 or packet[ihl + 1] != 0:
        return None

    reply = bytearray(packet[:total_length])

    source = bytes(reply[12:16])
    destination = bytes(reply[16:20])
    reply[12:16] = destination
    reply[16:20] = source
    reply[8] = 64

    reply[ihl] = 0
    reply[ihl + 2] = 0
    reply[ihl + 3] = 0
    checksum = internet_checksum(reply[ihl:total_length])
    reply[ihl + 2] = (checksum >> 8) & 0xFF
    reply[ihl + 3] = checksum & 0xFF

    reply[10] = 0
    reply[11] = 0
    checksum = internet_checksum(reply[:ihl])
    reply[10] = (checksum >> 8) & 0xFF
    reply[11] = checksum & 0xFF

    return bytes(reply)


class TunInterface:
    def __init__(self, name: str, address: str, mtu: int):
        self.name = name
        self.address = address
        self.mtu = mtu
        self.fd = -1

    def open(self) -> int:
        self.fd = os.open("/dev/net/tun", os.O_RDWR | os.O_NONBLOCK)
        ifreq = struct.pack("16sH", self.name.encode(), IFF_TUN | IFF_NO_PI)
        result = fcntl.ioctl(self.fd, TUNSETIFF, ifreq)
        actual_name = result[:16].split(b"\0", 1)[0].decode()
        self.name = actual_name

        subprocess.run(["ip", "addr", "flush", "dev", self.name], check=True)
        subprocess.run(["ip", "addr", "add", self.address, "dev", self.name], check=True)
        subprocess.run(["ip", "link", "set", "dev", self.name, "mtu", str(self.mtu)], check=True)
        subprocess.run(["ip", "link", "set", "dev", self.name, "up"], check=True)
        return self.fd

    def close(self) -> None:
        if self.fd >= 0:
            try:
                subprocess.run(
                    ["ip", "link", "set", "dev", self.name, "down"],
                    check=False,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
            finally:
                os.close(self.fd)
                self.fd = -1


class IpOverLinBridge:
    def __init__(
        self,
        *,
        socket_path: str,
        ifname: str,
        address: str,
        channel: int,
        baud: int,
        nodes: list[int],
        poll_ms: int,
        mtu: int,
        wire_loopback: bool,
        loopback_slave_channel: int,
    ):
        self.socket_path = socket_path
        self.ifname = ifname
        self.address = address
        self.channel = channel
        self.baud = baud
        self.nodes = nodes
        self.poll_ms = poll_ms
        self.mtu = mtu
        self.wire_loopback = wire_loopback
        self.loopback_slave_channel = loopback_slave_channel

        interface = ipaddress.IPv4Interface(address)
        if int(interface.ip) & 0xFF != 1:
            raise ValueError("master IPv4 address must end in .1")
        self.network = interface.network

        self.client = DaemonClient(socket_path)
        self.tun = TunInterface(ifname, address, mtu)
        self.selector = selectors.DefaultSelector()
        self.sequence = 1
        self.reassemblers = {node: Reassembler() for node in nodes}
        self.loopback_reply_frames: dict[int, deque[bytes]] = {
            node: deque() for node in nodes
        }

    def close(self) -> None:
        self.tun.close()
        self.client.close()

    def prepare_backend(self) -> None:
        # The current LIN socket API is implemented through Raw REPL.
        # Stop any autostart runtime before taking ownership of LIN.
        try:
            self.client.runtime_call("runtime_stop", timeout=1.0)
            time.sleep(0.1)
        except Exception:
            pass

        self.client.lin_init(self.channel, self.baud)
        if self.wire_loopback:
            self.client.lin_init(self.loopback_slave_channel, self.baud)

    def next_sequence(self) -> int:
        value = self.sequence
        self.sequence = (self.sequence + 1) & SEQ_MASK
        if self.sequence == 0:
            self.sequence = 1
        return value

    def packet_node(self, packet: bytes) -> int | None:
        if len(packet) < 20 or (packet[0] >> 4) != 4:
            return None

        destination = ipaddress.IPv4Address(packet[16:20])
        if destination not in self.network:
            return None

        node = int(destination) & 0xFF
        if node <= 1 or node > 63:
            return None
        return node

    def transmit_packet(self, packet: bytes) -> None:
        if len(packet) > self.mtu:
            return

        node = self.packet_node(packet)
        if node is None:
            return

        sequence = self.next_sequence()
        for frame in fragment_packet(packet, sequence):
            self.client.lin_send(self.channel, node, frame, enhanced=True)

        if self.wire_loopback:
            reply = icmp_echo_reply(packet, node)
            if reply is not None:
                queue = self.loopback_reply_frames[node]
                queue.clear()
                queue.extend(fragment_packet(reply, sequence))
                self.drain_wire_loopback(node)

    def drain_wire_loopback(self, node: int) -> None:
        queue = self.loopback_reply_frames[node]
        reassembler = self.reassemblers[node]

        while queue:
            frame = queue.popleft()
            self.client.lin_slave_set(
                self.loopback_slave_channel,
                node,
                frame,
                enhanced=True,
            )
            received = self.client.lin_request(
                self.channel,
                node,
                FRAME_SIZE,
                enhanced=True,
            )
            packet = reassembler.feed(received)
            if packet is not None:
                os.write(self.tun.fd, packet)

        self.client.lin_slave_clear(self.loopback_slave_channel)

    def poll_node(self, node: int) -> None:
        if self.wire_loopback:
            return

        try:
            frame = self.client.lin_request(
                self.channel,
                node,
                FRAME_SIZE,
                enhanced=True,
            )
        except (DaemonError, OSError, TimeoutError, RuntimeError, ValueError):
            return

        packet = self.reassemblers[node].feed(frame)
        if packet is not None:
            os.write(self.tun.fd, packet)

    def run(self) -> None:
        self.prepare_backend()
        fd = self.tun.open()
        self.selector.register(fd, selectors.EVENT_READ)

        node_index = 0
        timeout = max(self.poll_ms, 1) / 1000.0

        print(
            f"{self.tun.name}: {self.address}, LIN{self.channel}, "
            f"nodes={','.join(str(node) for node in self.nodes)}"
        )

        while True:
            events = self.selector.select(timeout)
            for key, _ in events:
                if key.fd != fd:
                    continue
                try:
                    packet = os.read(fd, self.mtu)
                except BlockingIOError:
                    continue
                if packet:
                    self.transmit_packet(packet)

            if self.nodes and not self.wire_loopback:
                node = self.nodes[node_index]
                node_index = (node_index + 1) % len(self.nodes)
                self.poll_node(node)


def parse_nodes(value: str) -> list[int]:
    nodes: list[int] = []
    for item in value.split(","):
        item = item.strip()
        if not item:
            continue
        node = int(item, 0)
        if node <= 1 or node > 63:
            raise argparse.ArgumentTypeError("LIN nodes must be in range 2..63")
        if node not in nodes:
            nodes.append(node)
    if not nodes:
        raise argparse.ArgumentTypeError("at least one LIN node is required")
    return nodes


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="beiis-lin-ip",
        description="Expose LIN nodes as IPv4 peers through a TUN interface",
    )
    parser.add_argument("--socket", default=DEFAULT_SOCKET_PATH)
    parser.add_argument("--ifname", default="lin0")
    parser.add_argument("--address", default="10.42.1.1/24")
    parser.add_argument("--channel", type=int, choices=(1, 2), default=1)
    parser.add_argument("--baud", type=int, default=19200)
    parser.add_argument("--nodes", type=parse_nodes, default=parse_nodes("2"))
    parser.add_argument("--poll-ms", type=int, default=20)
    parser.add_argument("--mtu", type=int, default=576)
    parser.add_argument(
        "--wire-loopback",
        action="store_true",
        help="use the other HAT LIN channel as a physical node-2 ICMP test peer",
    )
    parser.add_argument(
        "--loopback-slave-channel",
        type=int,
        choices=(1, 2),
        default=2,
    )
    args = parser.parse_args()

    if os.geteuid() != 0:
        parser.error("beiis-lin-ip must run as root to create/configure the TUN device")

    if args.wire_loopback and args.loopback_slave_channel == args.channel:
        parser.error("wire-loopback slave channel must differ from master channel")

    bridge = IpOverLinBridge(
        socket_path=args.socket,
        ifname=args.ifname,
        address=args.address,
        channel=args.channel,
        baud=args.baud,
        nodes=args.nodes,
        poll_ms=args.poll_ms,
        mtu=args.mtu,
        wire_loopback=args.wire_loopback,
        loopback_slave_channel=args.loopback_slave_channel,
    )

    try:
        bridge.run()
    except KeyboardInterrupt:
        return 0
    finally:
        bridge.close()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
