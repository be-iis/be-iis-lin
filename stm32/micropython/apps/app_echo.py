async def main(ctx):
    # Subscribe channels in the instance configuration, for example [0].
    while True:
        source, channel, payload = await ctx.recv()
        if source == "host":
            await ctx.send_host(channel, payload)
