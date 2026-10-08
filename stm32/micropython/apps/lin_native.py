BEIIS_API = 1

# Generic binary LIN RPC. It deliberately has no knowledge of the
# application protocol carried above it.
#
# request:
#   byte 0      operation
#   remaining   operation-specific payload
#
# reply:
#   byte 0      echoed operation
#   byte 1      status: 0=OK, 1=bad request, 2=LIN error, 3=internal error
#   remaining   operation-specific result / short error text
#
# Operations:
#   0x00 PING
#   0x01 INIT          baud:u32-le
#   0x02 SEND          id:u8 flags:u8 len:u8 data[len]
#   0x03 REQUEST       id:u8 flags:u8 len:u8
#   0x04 SLAVE_SET     id:u8 flags:u8 len:u8 data[len]
#   0x05 SLAVE_CLEAR
#   0x06 LEDS_GET
#   0x07 LEDS_SET      mask:u8
#   0x08 SLAVE_RX_SET  id:u8 flags:u8 len:u8
#   0x09 SLAVE_RX_RECV
#
# flags bit0: enhanced checksum (1); classic checksum (0)

OP_PING = 0x00
OP_INIT = 0x01
OP_SEND = 0x02
OP_REQUEST = 0x03
OP_SLAVE_SET = 0x04
OP_SLAVE_CLEAR = 0x05
OP_LEDS_GET = 0x06
OP_LEDS_SET = 0x07
OP_SLAVE_RX_SET = 0x08
OP_SLAVE_RX_RECV = 0x09

STATUS_OK = 0
STATUS_BAD_REQUEST = 1
STATUS_LIN_ERROR = 2
STATUS_INTERNAL = 3


def _u32le(data, offset=0):
    return (
        data[offset]
        | (data[offset + 1] << 8)
        | (data[offset + 2] << 16)
        | (data[offset + 3] << 24)
    )


def _reply(op, status=STATUS_OK, payload=b""):
    return bytes((op & 0xff, status & 0xff)) + bytes(payload)


def _error(op, status, exc):
    text = str(exc).encode()
    if len(text) > 120:
        text = text[:120]
    return _reply(op, status, text)


def handle_request(lin, channel, payload):
    payload = bytes(payload)
    if not payload:
        return _reply(0xff, STATUS_BAD_REQUEST, b"empty request")

    op = payload[0]

    try:
        if op == OP_PING:
            if len(payload) != 1:
                raise ValueError("PING length")
            return _reply(op)

        if op == OP_INIT:
            if len(payload) != 5:
                raise ValueError("INIT length")
            baud = _u32le(payload, 1)
            if baud <= 0:
                raise ValueError("invalid baud")
            lin.init(channel, baud)
            return _reply(op)

        if op == OP_SEND:
            if len(payload) < 4:
                raise ValueError("SEND length")
            frame_id = payload[1]
            enhanced = bool(payload[2] & 0x01)
            length = payload[3]
            if length > 8 or len(payload) != 4 + length:
                raise ValueError("SEND data length")
            lin.send(channel, frame_id, payload[4:], enhanced)
            return _reply(op)

        if op == OP_REQUEST:
            if len(payload) != 4:
                raise ValueError("REQUEST length")
            frame_id = payload[1]
            enhanced = bool(payload[2] & 0x01)
            length = payload[3]
            if length > 8:
                raise ValueError("REQUEST data length")
            data = lin.request(channel, frame_id, length, enhanced)
            return _reply(op, STATUS_OK, bytes((len(data),)) + data)

        if op == OP_SLAVE_SET:
            if len(payload) < 4:
                raise ValueError("SLAVE_SET length")
            frame_id = payload[1]
            enhanced = bool(payload[2] & 0x01)
            length = payload[3]
            if length > 8 or len(payload) != 4 + length:
                raise ValueError("SLAVE_SET data length")
            lin.slave_set(channel, frame_id, payload[4:], enhanced)
            return _reply(op)

        if op == OP_SLAVE_CLEAR:
            if len(payload) != 1:
                raise ValueError("SLAVE_CLEAR length")
            lin.slave_clear(channel)
            return _reply(op)

        if op == OP_LEDS_GET:
            if len(payload) != 1:
                raise ValueError("LEDS_GET length")
            return _reply(op, STATUS_OK, bytes((lin.leds(),)))

        if op == OP_LEDS_SET:
            if len(payload) != 2:
                raise ValueError("LEDS_SET length")
            return _reply(op, STATUS_OK, bytes((lin.leds(payload[1]),)))

        if op == OP_SLAVE_RX_SET:
            if len(payload) != 4:
                raise ValueError("SLAVE_RX_SET length")
            frame_id = payload[1]
            enhanced = bool(payload[2] & 0x01)
            length = payload[3]
            if length > 8:
                raise ValueError("SLAVE_RX_SET data length")
            lin.slave_rx_set(channel, frame_id, length, enhanced)
            return _reply(op)

        if op == OP_SLAVE_RX_RECV:
            if len(payload) != 1:
                raise ValueError("SLAVE_RX_RECV length")
            data = lin.slave_rx_recv(channel)
            if data is None:
                return _reply(op, STATUS_OK, b"\x00")
            data = bytes(data)
            return _reply(op, STATUS_OK, b"\x01" + bytes((len(data),)) + data)

        raise ValueError("unknown operation")

    except ValueError as exc:
        return _error(op, STATUS_BAD_REQUEST, exc)
    except OSError as exc:
        return _error(op, STATUS_LIN_ERROR, exc)
    except Exception as exc:
        return _error(op, STATUS_INTERNAL, exc)


async def main(ctx):
    import lin

    tx_peer = ctx.config.get("tx_peer")
    rx_peer = ctx.config.get("rx_peer")
    channel = int(ctx.config.get("lin_channel", 0))
    baud = int(ctx.config.get("baud", 19200))

    if not isinstance(tx_peer, str) or not tx_peer:
        raise ValueError("tx_peer is required")
    if not isinstance(rx_peer, str) or not rx_peer:
        raise ValueError("rx_peer is required")
    if channel not in (1, 2):
        raise ValueError("lin_channel must be 1 or 2")
    if baud <= 0:
        raise ValueError("invalid baud")

    lin.init(channel, baud)

    while True:
        source, app_channel, payload = await ctx.recv()
        if source != tx_peer:
            continue

        reply = handle_request(lin, channel, payload)
        ctx.send_to(rx_peer, reply, app_channel)
