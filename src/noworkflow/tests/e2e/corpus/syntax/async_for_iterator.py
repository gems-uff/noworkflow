"""async for over an asynchronous iterator defined by a class, with an else
clause; over an asynchronous generator it is in async_for.py"""
import asyncio


class Countdown:
    def __init__(self, start):
        self.start = start

    def __aiter__(self):
        return self

    async def __anext__(self):
        if self.start <= 0:
            raise StopAsyncIteration
        self.start -= 1
        return self.start + 1


async def main():
    async for value in Countdown(3):
        print("value", value)
    else:
        print("done")


asyncio.run(main())
