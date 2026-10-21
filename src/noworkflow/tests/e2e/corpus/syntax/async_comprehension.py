"""An asynchronous comprehension: async for inside a list comprehension
(PEP 530, #157), over the lines of an asyncio.StreamReader, whose
asynchronous iteration is not traced; over an asynchronous generator or
iterator of the script it is in async_for.py and async_for_iterator.py, and
await in a comprehension is in async_await_comprehension.py"""
import asyncio


async def main():
    reader = asyncio.StreamReader()
    reader.feed_data(b"0\n1\n2\n3\n")
    reader.feed_eof()
    evens = [int(line) async for line in reader if int(line) % 2 == 0]
    print(evens)


asyncio.run(main())
