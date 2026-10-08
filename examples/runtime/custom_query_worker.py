BEIIS_API = 1


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

        reply = b"reply:" + bytes(payload).upper()
        ctx.send_to(rx_peer, reply, channel)
