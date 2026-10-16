"""Name binding and scopes

Closures and their cells, late binding of closures created in a loop,
``nonlocal`` counters, ``global`` updates from a function, the scope of
comprehension variables, class bodies that do not leak into methods,
``del`` of names, items, slices and attributes, ``UnboundLocalError``,
a name never bound because its loop body never ran, a shadowed builtin and
its restoration, nested function factories, and annotated assignments of
names and attributes. The transformer does not rewrite ``del`` yet
(visit_Delete, transformer_stmt.py, records the statement and returns it
unchanged), so those statements compare plain Python with plain Python
until it does; what the script reads afterwards is traced.
Split out: lambdas inside collection displays (lambda_in_collection.py),
comprehensions in a class body (class_body_comprehension.py),
``globals()``, ``locals()``, ``vars()`` and ``dir()`` without arguments
(caller_frame.py) and ``__builtins__`` (builtins_module.py). Under
``-cg``: #275 (``self.reading: float = start`` and
``self.history: list = []``).
"""
total = 0
LIMIT = 3


def make_counter(start):
    count = start

    def increment(step=1):
        nonlocal count
        count += step
        return count

    def peek():
        return count

    return increment, peek


increment, peek = make_counter(10)
increment()
increment(5)
print(peek(), increment.__closure__ is not None)
other, other_peek = make_counter(0)
other()
print(peek(), other_peek())


def add_to_total(amount):
    global total
    total += amount
    return total


for amount in (1, 2, 3):
    add_to_total(amount)
print("total", total)


def reads_global():
    return LIMIT * 2


LIMIT = 7
print(reads_global())

late = []
for index in range(3):
    def show():
        return index
    late.append(show)
early = []
for index in range(3):
    def bind(value=index):
        return value
    early.append(bind)
print([func() for func in late], [func() for func in early])


def make_multipliers():
    result = []
    for factor in range(1, 4):
        def multiply(value, factor=factor):
            return value * factor
        result.append(multiply)
    return result


print([multiply(10) for multiply in make_multipliers()])

x = "outer"
squares = [x * 2 for x in range(3)]
print(x, squares)
pairs = {(x, y) for x in range(2) for y in "ab"}
print(sorted(pairs), x)


class Config:
    name = "config"
    upper = name.upper()
    for suffix in ("a", "b"):
        upper += suffix

    def describe(self):
        try:
            return upper
        except NameError as error:
            return "{}/{} ({})".format(self.name, Config.upper, error)


print(Config.suffix, Config().describe())


def shadowing(values):
    list = sorted
    return list(values)


print(shadowing({3, 1, 2}), list("ab"))
len = lambda value: -1
print(len("abc"))
del len
print(len("abc"))


def unbound():
    try:
        print(counter)
        counter = 1
    except UnboundLocalError as error:
        return "{}: {}".format(type(error).__name__, error)
    return counter


print(unbound())

data = {"a": 1, "b": 2, "c": 3}
del data["b"]
numbers = list(range(10))
del numbers[2:8:2]
del numbers[0]
temporary = "gone"
del temporary
try:
    print(temporary)
except NameError as error:
    print("temporary deleted:", error, data, numbers)


class Bag:
    pass


bag = Bag()
bag.item = 1
bag.other = 2
del bag.item
print(hasattr(bag, "item"), bag.other)
a, b = 1, 2
del a, b
try:
    print(a)
except NameError as error:
    print("deleted:", error)
try:
    print(b)
except NameError as error:
    print("deleted:", error)
print("item" in vars(bag))


def outer():
    message = "from outer"

    def middle():
        def inner():
            return message.upper()
        return inner()

    return middle()


print(outer())


def accumulate():
    items = []

    def add(item):
        items.append(item)
        return len(items)

    add("x")
    add("y")
    return items


print(accumulate(), accumulate())

if True:
    block_variable = "visible after the block"
for loop_variable in range(2):
    pass
while False:
    never = 1
print(block_variable, loop_variable)
try:
    print(never)
except NameError as error:
    print("never bound:", error)

limit: int = 3
label: str
label = "annotated"


class Gauge:
    reading: float = 0.0

    def __init__(self, start):
        self.reading: float = start
        self.history: list = []

    def record(self, value):
        self.history.append(self.reading)
        self.reading = value
        return self


gauge = Gauge(1.5).record(2.5).record(limit)
print(label, limit, gauge.reading, gauge.history, Gauge.reading)
