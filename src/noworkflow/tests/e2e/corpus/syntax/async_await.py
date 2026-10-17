"""async def and await: a coroutine without parameters, one with a
parameter, and asyncio.gather (#266, reached through the uninstrumented
await of #157)"""
import asyncio


async def ready():
    await asyncio.sleep(0)
    return "ready"


async def double(value):
    await asyncio.sleep(0)
    return value * 2


async def main():
    first = await double(2)
    results = await asyncio.gather(double(3), double(4))
    print(first, results)
    print(await ready())


asyncio.run(main())
