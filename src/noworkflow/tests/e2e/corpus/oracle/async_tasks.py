"""Coroutines driven by asyncio (#266, reached through #157)

``async def`` functions awaited in sequence and gathered concurrently, an
``asyncio.Queue`` between a producer and a consumer, ``async with`` over an
async context manager, and a timeout that the script catches. Every sleep
is zero; only the timeout waits, for a hundredth of a second. ``async
for`` and async comprehensions are left to the syntax corpus (#157).
"""
import asyncio

EVENTS = []


async def fetch(name, steps):
    for step in range(steps):
        EVENTS.append("{} step {}".format(name, step))
        await asyncio.sleep(0)
    return name.upper()


class Session:
    def __init__(self, name):
        self.name = name
        self.open = False

    async def __aenter__(self):
        self.open = True
        EVENTS.append("open " + self.name)
        return self

    async def __aexit__(self, kind, value, traceback):
        self.open = False
        EVENTS.append("close " + self.name)
        return False


async def producer(queue, items):
    for item in items:
        await queue.put(item)
    await queue.put(None)


async def consumer(queue, seen):
    while True:
        item = await queue.get()
        if item is None:
            return len(seen)
        seen.append(item * 10)


async def never_finishes():
    await asyncio.Event().wait()


async def main():
    first = await fetch("solo", 1)
    results = await asyncio.gather(fetch("a", 2), fetch("b", 3))
    print(first, results)
    print(EVENTS)
    async with Session("db") as session:
        print("inside", session.open)
    print("after", session.open, EVENTS[-2:])
    queue = asyncio.Queue()
    seen = []
    produced, consumed = await asyncio.gather(
        producer(queue, [1, 2, 3]), consumer(queue, seen))
    print(produced, consumed, seen)
    try:
        await asyncio.wait_for(never_finishes(), timeout=0.01)
    except asyncio.TimeoutError:
        print("timed out")
    return "done"


print(asyncio.run(main()))
