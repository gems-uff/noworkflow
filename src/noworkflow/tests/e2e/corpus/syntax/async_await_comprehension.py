"""await inside a list comprehension of a coroutine (PEP 530; #266, reached
through the uninstrumented await of #157)"""
import asyncio


async def square(value):
    return value * value


async def main():
    squares = [await square(value) for value in range(3)]
    print(squares)


asyncio.run(main())
