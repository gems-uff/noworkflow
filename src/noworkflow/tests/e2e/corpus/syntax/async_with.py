"""async with over asynchronous context managers, two items in one
statement (#266, reached through the uninstrumented async with of #157)"""
import asyncio


class Resource:
    def __init__(self, name):
        self.name = name

    async def __aenter__(self):
        print("enter", self.name)
        return self.name.upper()

    async def __aexit__(self, *exc_info):
        print("exit", self.name)
        return False


async def main():
    async with Resource("a") as first, Resource("b") as second:
        print("inside", first, second)


asyncio.run(main())
