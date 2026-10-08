from __future__ import annotations

import argparse
import fcntl
import ipaddress
import os
import selectors
import struct
import subprocess
import time

from beiis_lin.client import DaemonClient, DaemonError
from beiis_lin.socket_protocol import DEFAULT_SOCKET_PATH


TUNSETIFF = 0x400454CA
TUNSETOFFLOAD = 0x400454D0
TUN_READ_SIZE = 65535
IFF_TUN = 0x0001
IFF_NO_PI = 0x1000

FRAME_SIZE = 8
HEADER_SIZE = 2
PAYLOAD_SIZE = FRAME_SIZE - HEADER_SIZE
SEQ_MASK = 0x3F
FLAG_END = 0x40
FLAG_START = 0x80

RPC_PING = 0x00
RPC_INIT = 0x01
RPC_SEND = 0x02
RPC_REQUEST = 0x03
RPC_SLAVE_SET = 0x04
RPC_SLAVE_CLEAR = 0x05
RPC_SLAVE_RX_SET = 0x08
RPC_SLAVE_RX_RECV = 0x09

MASTER_TX_SLOT = 0
MASTER_RX_SLOT = 1
SLAVE_TX_SLOT = 3
SLAVE_RX_SLOT = 4
APP_CHANNEL = 0


def downlink_id(node: int) -> int:
    node = int(node)
    if node < 2 or node > 31:
        raise ValueError("node must be 2..31")
    return node


def uplink_id(node: int) -> int:
    return downlink_id(node) | 0x20


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


class RuntimeLinClient:
    def __init__(self, client, tx_slot, rx_slot, app_channel=APP_CHANNEL):
        self.client = client
        self.tx_slot = int(tx_slot)
        self.rx_slot = int(rx_slot)
        self.app_channel = int(app_channel)

    def call(self, request: bytes, timeout: float = 2.0) -> bytes:
        request = bytes(request)
        if not request:
            raise ValueError("empty runtime LIN request")

        self.client.set_active_instance(self.tx_slot)
        self.client.data_send(self.app_channel, request)
        instance, channel, reply = self.client.data_recv(
            instance=self.rx_slot,
            channel=self.app_channel,
            timeout=timeout,
        )

        if instance != self.rx_slot or channel != self.app_channel:
            raise RuntimeError("unexpected runtime LIN reply source")
        if len(reply) < 2:
            raise RuntimeError("short runtime LIN reply")
        if reply[0] != request[0]:
            raise RuntimeError("runtime LIN operation mismatch")
        if reply[1] != 0:
            text = reply[2:].decode("utf-8", "replace")
            raise RuntimeError(
                f"runtime LIN operation 0x{request[0]:02x} failed "
                f"status={reply[1]}: {text}"
            )
        return bytes(reply[2:])

    def ping(self) -> None:
        self.call(bytes((RPC_PING,)))

    def init(self, baud: int) -> None:
        self.call(bytes((RPC_INIT,)) + int(baud).to_bytes(4, "little"))

    def send(self, frame_id: int, data: bytes, enhanced: bool = True) -> None:
        data = bytes(data)
        if len(data) > 8:
            raise ValueError("LIN data > 8 bytes")
        flags = 1 if enhanced else 0
        self.call(bytes((RPC_SEND, frame_id & 0x3F, flags, len(data))) + data)

    def request(
        self,
        frame_id: int,
        length: int,
        enhanced: bool = True,
        timeout: float = 2.0,
    ) -> bytes:
        if length < 0 or length > 8:
            raise ValueError("LIN request length must be 0..8")
        flags = 1 if enhanced else 0
        result = self.call(
            bytes((RPC_REQUEST, frame_id & 0x3F, flags, length)),
            timeout=timeout,
        )
        if not result:
            raise RuntimeError("missing LIN request result length")
        received = result[0]
        data = result[1:]
        if received != len(data):
            raise RuntimeError("invalid LIN request result length")
        return data

    def slave_set(self, frame_id: int, data: bytes, enhanced: bool = True) -> None:
        data = bytes(data)
        if len(data) > 8:
            raise ValueError("LIN data > 8 bytes")
        flags = 1 if enhanced else 0
        self.call(
            bytes((RPC_SLAVE_SET, frame_id & 0x3F, flags, len(data))) + data
        )

    def slave_clear(self) -> None:
        self.call(bytes((RPC_SLAVE_CLEAR,)))

    def slave_rx_set(
        self, frame_id: int, length: int, enhanced: bool = True
    ) -> None:
        if length < 0 or length > 8:
            raise ValueError("LIN receive length must be 0..8")
        flags = 1 if enhanced else 0
        self.call(
            bytes((RPC_SLAVE_RX_SET, frame_id & 0x3F, flags, length))
        )

    def slave_rx_recv(self) -> bytes | None:
        result = self.call(bytes((RPC_SLAVE_RX_RECV,)))
        if result == b"\x00":
            return None
        if len(result) < 2 or result[0] != 1:
            raise RuntimeError("invalid slave receive result")
        length = result[1]
        data = result[2:]
        if len(data) != length:
            raise RuntimeError("invalid slave receive data length")
        return data


class TunInterface:
    def __init__(self, name: str, address: str, mtu: int):
        self.name = name
        self.address = address
        self.mtu = mtu
        self.fd = -1

    def _create(self) -> int:
        self.fd = os.open("/dev/net/tun", os.O_RDWR | os.O_NONBLOCK)
        ifreq = struct.pack("16sH", self.name.encode(), IFF_TUN | IFF_NO_PI)
        result = fcntl.ioctl(self.fd, TUNSETIFF, ifreq)
        self.name = result[:16].split(b"\0", 1)[0].decode()
        # Do not allow GSO/TSO/USO packets to reach this userspace link.
        # The LIN framing layer requires one ordinary IPv4 packet at a time.
        fcntl.ioctl(self.fd, TUNSETOFFLOAD, 0)
        return self.fd

    def open(self) -> int:
        self._create()
        subprocess.run(["ip", "addr", "flush", "dev", self.name], check=True)
        subprocess.run(["ip", "addr", "add", self.address, "dev", self.name], check=True)
        subprocess.run(
            ["ip", "link", "set", "dev", self.name, "mtu", str(self.mtu)],
            check=True,
        )
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


class NamespaceTunInterface(TunInterface):
    def __init__(
        self,
        name: str,
        address: str,
        mtu: int,
        namespace: str,
    ):
        super().__init__(name, address, mtu)
        self.namespace = namespace

    def open(self) -> int:
        subprocess.run(
            ["ip", "netns", "del", self.namespace],
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        subprocess.run(["ip", "netns", "add", self.namespace], check=True)

        self._create()
        subprocess.run(
            ["ip", "link", "set", "dev", self.name, "netns", self.namespace],
            check=True,
        )
        subprocess.run(
            ["ip", "-n", self.namespace, "link", "set", "lo", "up"],
            check=True,
        )
        subprocess.run(
            ["ip", "-n", self.namespace, "addr", "add", self.address, "dev", self.name],
            check=True,
        )
        subprocess.run(
            [
                "ip", "-n", self.namespace, "link", "set", "dev", self.name,
                "mtu", str(self.mtu),
            ],
            check=True,
        )
        subprocess.run(
            ["ip", "-n", self.namespace, "link", "set", "dev", self.name, "up"],
            check=True,
        )
        return self.fd

    def close(self) -> None:
        if self.fd >= 0:
            os.close(self.fd)
            self.fd = -1
        subprocess.run(
            ["ip", "netns", "del", self.namespace],
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )


class IpOverLinBridge:
    def __init__(
        self,
        *,
        socket_path: str,
        ifname: str,
        address: str,
        baud: int,
        nodes: list[int],
        poll_ms: int,
        mtu: int,
        wire_loopback: bool,
        node_namespace: str,
        node_ifname: str,
        node_address: str,
    ):
        self.address = address
        self.baud = baud
        self.nodes = nodes
        self.poll_ms = poll_ms
        self.mtu = mtu
        self.wire_loopback = wire_loopback

        interface = ipaddress.IPv4Interface(address)
        if int(interface.ip) & 0xFF != 1:
            raise ValueError("master IPv4 address must end in .1")
        self.network = interface.network

        if wire_loopback and len(nodes) != 1:
            raise ValueError("wire-loopback currently supports exactly one node")

        self.client = DaemonClient(socket_path)
        self.master = RuntimeLinClient(
            self.client, MASTER_TX_SLOT, MASTER_RX_SLOT, APP_CHANNEL
        )
        self.slave = RuntimeLinClient(
            self.client, SLAVE_TX_SLOT, SLAVE_RX_SLOT, APP_CHANNEL
        )

        self.master_tun = TunInterface(ifname, address, mtu)
        self.node_tun = None
        if wire_loopback:
            node_iface = ipaddress.IPv4Interface(node_address)
            expected_node = nodes[0]
            if node_iface.network != interface.network:
                raise ValueError("node endpoint must be in the same IPv4 subnet")
            if (int(node_iface.ip) & 0xFF) != expected_node:
                raise ValueError("node endpoint host octet must equal the LIN node")
            self.node_tun = NamespaceTunInterface(
                node_ifname,
                node_address,
                mtu,
                node_namespace,
            )

        self.selector = selectors.DefaultSelector()
        self.sequence = 1
        self.master_reassemblers = {node: Reassembler() for node in nodes}
        self.slave_reassemblers = {node: Reassembler() for node in nodes}

    def close(self) -> None:
        try:
            self.selector.close()
        finally:
            if self.node_tun is not None:
                self.node_tun.close()
            self.master_tun.close()
            self.client.close()

    def prepare_backend(self) -> None:
        info = self.client.runtime_call("info", timeout=2.0)
        expected = {
            "master_tx_query": MASTER_TX_SLOT,
            "master_rx_query": MASTER_RX_SLOT,
            "slave_tx_query": SLAVE_TX_SLOT,
            "slave_rx_query": SLAVE_RX_SLOT,
        }
        found = {
            item.get("name"): item
            for item in (info.get("instances") or [])
        }

        for name, slot in expected.items():
            item = found.get(name)
            if item is None:
                raise RuntimeError(
                    f"missing runtime instance {name}; "
                    "run scripts/install-standard-runtime.py first"
                )
            if int(item.get("slot", -1)) != slot:
                raise RuntimeError(
                    f"runtime instance {name} is in slot {item.get('slot')}, "
                    f"expected {slot}"
                )
            if item.get("state") != "running":
                raise RuntimeError(
                    f"runtime instance {name} is not running: {item.get('state')}"
                )

        self.master.ping()
        self.master.init(self.baud)

        if self.wire_loopback:
            slave_native = found.get("slave_native")
            if slave_native is None or slave_native.get("state") != "running":
                raise RuntimeError("slave_native is not running")
            self.slave.ping()
            self.slave.init(self.baud)
            node = self.nodes[0]
            self.slave.slave_rx_set(
                downlink_id(node),
                FRAME_SIZE,
                enhanced=True,
            )

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
        if node not in self.nodes:
            return None
        return node

    def wait_slave_rx(self, timeout: float = 1.0) -> bytes:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            data = self.slave.slave_rx_recv()
            if data is not None:
                return data
            time.sleep(0.001)
        raise TimeoutError("timeout waiting for slave receive frame")

    def master_to_node(self, packet: bytes) -> None:
        if len(packet) > self.mtu:
            print(
                f"drop master packet: {len(packet)} bytes exceeds MTU {self.mtu}",
                flush=True,
            )
            return

        node = self.packet_node(packet)
        if node is None:
            return

        sequence = self.next_sequence()

        if not self.wire_loopback:
            for frame in fragment_packet(packet, sequence):
                self.master.send(downlink_id(node), frame, enhanced=True)
            return

        reassembler = self.slave_reassemblers[node]
        complete = None
        for frame in fragment_packet(packet, sequence):
            self.master.send(downlink_id(node), frame, enhanced=True)
            received = self.wait_slave_rx()
            complete = reassembler.feed(received)

        if complete is not None and self.node_tun is not None:
            os.write(self.node_tun.fd, complete)

    def node_to_master(self, node: int, packet: bytes) -> None:
        if len(packet) > self.mtu:
            print(
                f"drop node packet: {len(packet)} bytes exceeds MTU {self.mtu}",
                flush=True,
            )
            return

        sequence = self.next_sequence()
        reassembler = self.master_reassemblers[node]
        complete = None
        response_id = uplink_id(node)

        try:
            for frame in fragment_packet(packet, sequence):
                self.slave.slave_set(response_id, frame, enhanced=True)
                received = self.master.request(
                    response_id,
                    FRAME_SIZE,
                    enhanced=True,
                    timeout=2.0,
                )
                complete = reassembler.feed(received)
        finally:
            self.slave.slave_clear()

        if complete is not None:
            os.write(self.master_tun.fd, complete)

    def poll_node(self, node: int) -> None:
        try:
            frame = self.master.request(
                uplink_id(node),
                FRAME_SIZE,
                enhanced=True,
                timeout=0.2,
            )
        except (DaemonError, OSError, TimeoutError, RuntimeError, ValueError):
            return

        packet = self.master_reassemblers[node].feed(frame)
        if packet is not None:
            os.write(self.master_tun.fd, packet)

    def run(self) -> None:
        self.prepare_backend()

        master_fd = self.master_tun.open()
        self.selector.register(master_fd, selectors.EVENT_READ, ("master", None))

        if self.node_tun is not None:
            node_fd = self.node_tun.open()
            self.selector.register(
                node_fd,
                selectors.EVENT_READ,
                ("node", self.nodes[0]),
            )

        timeout = max(self.poll_ms, 1) / 1000.0
        node_index = 0

        print(
            f"{self.master_tun.name}: {self.address}, "
            f"nodes={','.join(str(node) for node in self.nodes)}"
        )
        if self.node_tun is not None:
            print(
                f"{self.node_tun.namespace}/{self.node_tun.name}: "
                f"{self.node_tun.address}"
            )

        while True:
            events = self.selector.select(timeout)
            for key, _ in events:
                side, node = key.data
                try:
                    packet = os.read(key.fd, TUN_READ_SIZE)
                except BlockingIOError:
                    continue
                if not packet:
                    continue

                if side == "master":
                    self.master_to_node(packet)
                else:
                    self.node_to_master(int(node), packet)

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
        if node < 2 or node > 31:
            raise argparse.ArgumentTypeError("LIN nodes must be in range 2..31")
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
    parser.add_argument("--baud", type=int, default=19200)
    parser.add_argument("--nodes", type=parse_nodes, default=parse_nodes("2"))
    parser.add_argument("--poll-ms", type=int, default=20)
    parser.add_argument("--mtu", type=int, default=576)
    parser.add_argument(
        "--wire-loopback",
        action="store_true",
        help="use LIN2 as a real node endpoint behind a second Linux namespace",
    )
    parser.add_argument("--node-namespace", default="beiis-lin-node2")
    parser.add_argument("--node-ifname", default="lin-node2")
    parser.add_argument("--node-address", default="10.42.1.2/24")
    args = parser.parse_args()

    if os.geteuid() != 0:
        parser.error("beiis-lin-ip must run as root to create/configure TUN devices")

    bridge = IpOverLinBridge(
        socket_path=args.socket,
        ifname=args.ifname,
        address=args.address,
        baud=args.baud,
        nodes=args.nodes,
        poll_ms=args.poll_ms,
        mtu=args.mtu,
        wire_loopback=args.wire_loopback,
        node_namespace=args.node_namespace,
        node_ifname=args.node_ifname,
        node_address=args.node_address,
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
