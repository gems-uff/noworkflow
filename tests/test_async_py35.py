import asyncio


def func(obj):
    return obj


def dec(obj):
    return obj


@dec
async def function(param):
    print('function {} 1'.format(param))
    await asyncio.sleep(0.01)
    print('function {} 2'.format(param))


class AsyncFeatures(object):

    def __init__(self):
        self.i = 0

    async def __aenter__(self):
        await function("enter")

    async def __aexit__(self, exc_type, exc, traceback):
        await function("exit")

    async def __aiter__(self):
        self.i = 0
        return self

    async def __anext__(self):
        self.i += 1
        if self.i > 3:
            raise StopAsyncIteration
        await function("next {}".format(self.i))
        return self.i

    @dec
    async def method(self):
        async with self:
            await function("method A")
            await function("method B")
        await function("method C")
        async for i in self:
            await function("for {}".format(i))

async def other():
    obj = AsyncFeatures()
    await obj.method()

loop = asyncio.get_event_loop()
loop.run_until_complete(other())
