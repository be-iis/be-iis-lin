BEIIS_API = 1

# Generic logging worker.
#
# This worker intentionally does not pretend that passive LIN reception exists.
# It provides the same tx/rx query topology as the LIN workers and can carry
# logger control/status messages. Native passive RX can be attached here later
# without changing the host/application interface.

OP_PING = 0x00
OP_STATUS = 0x01

STATUS_OK = 0
STATUS_UNSUPPORTED = 4


def _reply(op, status=STATUS_OK, payload=b""):
    return bytes((op & 0xff, status & 0xff)) + bytes(payload)


async def main(ctx):
    tx_peer = ctx.config.get("tx_peer")
    rx_peer = ctx.config.get("rx_peer")

    if not isinstance(tx_peer, str) or not tx_peer:
        raise ValueError("tx_peer is required")
    if not isinstance(rx_peer, str) or not rx_peer:
        raise ValueError("rx_peer is required")

    while True:
        source, channel, payload = await ctx.recv()
        if source != tx_peer:
            continue

        payload = bytes(payload)
        if not payload:
            reply = _reply(0xff, STATUS_UNSUPPORTED, b"empty request")
        elif payload[0] == OP_PING:
            reply = _reply(OP_PING)
        elif payload[0] == OP_STATUS:
            # Passive native receive is not implemented yet.
            reply = _reply(OP_STATUS, STATUS_UNSUPPORTED, b"passive RX unavailable")
        else:
            reply = _reply(payload[0], STATUS_UNSUPPORTED, b"unsupported logging op")

        ctx.send_to(rx_peer, reply, channel)
