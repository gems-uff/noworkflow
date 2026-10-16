"""Generators and iterators

Laziness and the order of side effects, ``send``/``throw``/``close``,
``yield from`` that delegates ``send`` and receives a return value,
generator expressions (consumed once, with their late binding), an
iterator class, an asynchronous iterator class consumed by ``async for``
in a coroutine driven by hand, ``itertools`` pipelines, and a generator
left by ``break`` and closed by hand. Split out: a parameterless generator
under ``yield from`` (yield_from_builtin.py), an iterator class given to
``zip`` (callbacks.py), a generator closed by being dropped
(dropped_generator.py), a ``yield`` inside a call's arguments
(yield_in_call_argument.py), a generator expression whose first iterable
changes after it was created or raises (genexp_iterable_snapshot.py and
genexp_iterable_raises.py), and coroutines driven by ``asyncio``
(async_tasks.py). Under ``-cg``: #275
(``self.current -= 1`` in ``Countdown``).
"""
import itertools

events = []


def numbers(limit):
    for value in range(limit):
        events.append("produce %d" % value)
        yield value
    events.append("exhausted")


lazy = numbers(3)
events.append("created")
for value in lazy:
    events.append("consume %d" % value)
print(events)


def running_total(start):
    total = start
    while True:
        received = yield total
        if received is None:
            return total
        total += received


accumulator = running_total(0)
print(next(accumulator), accumulator.send(5), accumulator.send(7))
try:
    accumulator.send(None)
except StopIteration as stop:
    print("returned", stop.value)


def delegator(start):
    result = yield from running_total(start)
    yield "delegated total %d" % result


chain = delegator(100)
print(next(chain), chain.send(1), chain.send(2), chain.send(None))


def guarded(limit):
    try:
        for value in range(limit):
            try:
                yield value
            except KeyError as error:
                yield "recovered from %s" % error
    finally:
        events.append("guarded closed")


events.clear()
guard = guarded(5)
print(next(guard), next(guard), guard.throw(KeyError("k")), next(guard))
guard.close()
print(events, guard.gi_frame is None)

partial = guarded(10)
for value in partial:
    if value == 2:
        break
print(events)
partial.close()
print(events)

squares = (n * n for n in range(5))
print(sum(squares), sum(squares))
multiplier = 2
scaled = (n * multiplier for n in range(3))
multiplier = 10
print(list(scaled))


class Countdown:
    def __init__(self, start):
        self.current = start

    def __iter__(self):
        return self

    def __next__(self):
        if self.current <= 0:
            raise StopIteration
        self.current -= 1
        return self.current + 1


labels = []
for number in Countdown(3):
    labels.append("t-%d" % number)
print(list(Countdown(4)), labels, sum(Countdown(5)))
pairs = itertools.islice(itertools.count(1, 2), 4)
print(list(pairs), list(itertools.accumulate([1, 2, 3, 4])))
print(list(itertools.chain.from_iterable([[1], [2, 3], []])))
grouped = itertools.groupby(sorted("mississippi"))
print([(key, len(list(group))) for key, group in grouped])


class Ticker:
    def __init__(self, count):
        self.count = count

    def __aiter__(self):
        return self

    async def __anext__(self):
        if self.count == 0:
            raise StopAsyncIteration
        self.count -= 1
        return self.count


async def collect_ticks(ticker):
    ticks = []
    async for tick in ticker:
        ticks.append(tick)
    return ticks


def run_to_completion(coroutine):
    try:
        coroutine.send(None)
    except StopIteration as stop:
        return stop.value
    raise RuntimeError("the coroutine awaited something")


print(run_to_completion(collect_ticks(Ticker(3))))


def fibonacci(limit):
    a, b = 0, 1
    while a < limit:
        yield a
        a, b = b, a + b


print(list(fibonacci(100)), max(fibonacci(1000)))
print(dict(enumerate(fibonacci(10), start=1)))
