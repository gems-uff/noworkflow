"""async for over an asynchronous generator, with an else clause (#157);
over an iterator defined by a class it is in async_for_iterator.py"""
import asyncio


async def countdown(start):
    while start > 0:
        yield start
        start -= 1


async def main():
    async for value in countdown(3):
        print("value", value)
    else:
        print("done")


asyncio.run(main())
