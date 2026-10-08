BEIIS_API = 1


async def main(ctx):
    direction = str(ctx.config.get("direction", "")).lower()
    peer = ctx.config.get("peer")

    if direction not in ("tx", "rx"):
        raise ValueError("query direction must be 'tx' or 'rx'")
    if not isinstance(peer, str) or not peer:
        raise ValueError("query peer is required")

    while True:
        source, channel, payload = await ctx.recv()

        if direction == "tx":
            # Host/application -> native worker.
            # Ignore local messages so a routing mistake cannot loop forever.
            if source == "host":
                if not ctx.send_to(peer, payload, channel):
                    await ctx.send_host(channel, b"\xffpeer unavailable")
        else:
            # Native worker -> host/application.
            # Only the configured native peer is allowed to publish replies.
            if source == peer:
                await ctx.send_host(channel, payload)
