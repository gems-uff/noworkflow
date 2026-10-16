"""Evaluation order and side effects

Each traced expression is evaluated by noWorkflow's wrappers, so the order
and the number of evaluations must not change: call arguments left to right,
dict displays, chained comparisons that evaluate the middle operand once,
short-circuit ``and``/``or``, conditional expressions, ``if``/``elif``/
``else`` chains in a function and at module level, augmented assignment
to a subscript and to an attribute whose index or object is computed by a
call, chained assignment, tuple swap, starred targets, and the ``else``
clauses of ``for`` and ``while`` with and without ``break``. Under
``-cg``: #NEW:coarse-augassign-target (``counts[note("index", 1)] += ...``).
"""
log = []


def note(tag, value):
    log.append(tag)
    return value


def flush(title):
    print(title, " ".join(log))
    log.clear()


def triple(a, b, c):
    return a + b + c


triple(note("a", 1), note("b", 2), note("c", 3))
flush("arguments:")

config = {note("k1", "x"): note("v1", 1), note("k2", "y"): note("v2", 2)}
flush("dict display:")
print(list(config.items()))

print(note("low", 1) < note("mid", 5) < note("high", 9))
flush("chained true:")
print(note("low", 1) < note("mid", 0) < note("high", 9))
flush("chained false:")

print(note("f", 0) and note("never", 1), note("t", 1) or note("never", 2))
flush("short circuit:")
print(note("first", "") or note("second", "") or note("third", "x"))
flush("or chain:")

print(note("yes", "a") if note("cond", True) else note("no", "b"))
flush("conditional:")


def classify(number):
    if note("negative?", number < 0):
        return "negative"
    elif note("zero?", number == 0):
        return "zero"
    elif note("small?", number < 10):
        return "small"
    else:
        note("large", number)
        return "large"


print([classify(number) for number in (-5, 0, 7, 42)])
flush("if chain:")

for number in range(4):
    if note("even?", number % 2 == 0):
        parity = "even"
    else:
        parity = "odd"
    print(number, parity)
flush("module if:")

counts = [0, 0, 0]
counts[note("index", 1)] += note("step", 5)
flush("augmented subscript:")
print(counts)


class Box:
    def __init__(self):
        self.total = 10


boxes = [Box(), Box()]
note("pick", boxes)[note("which", 0)].total -= note("amount", 3)
flush("augmented attribute:")
print([box.total for box in boxes])

first = second = note("shared", [])
first.append(1)
flush("chained assignment:")
print(first is second, second)

left, right = note("l", "L"), note("r", "R")
left, right = right, left
flush("swap:")
print(left, right)

head, *middle, last = note("seq", range(6))
flush("starred:")
print(head, middle, last)
(a, b), c = note("nested", ((1, 2), 3))
print(a, b, c)

items = [3, 1, 2]
items[note("i0", 0)], items[note("i1", 1)] = items[1], items[0]
flush("subscript targets:")
print(items)

matrix = [[0] * 3 for _ in range(3)]
for row in range(3):
    for col in range(3):
        matrix[row][col] = row * 3 + col
print(matrix[note("r", 2)][note("c", 1)], sum(map(sum, matrix)))
flush("nested subscript:")

value = 0
value += note("one", 1)
value *= note("ten", 10)
value **= 2
value //= 7
value %= 11
value <<= 2
value |= 1
value ^= 3
print(value)
flush("augmented operators:")


def first_multiple(values, divisor):
    for value in values:
        if value % divisor == 0:
            note("found", value)
            break
        note("skip", value)
    else:
        note("none", divisor)
        return None
    return value


print(first_multiple([3, 5, 8, 9], 4), first_multiple([1, 3], 2))
flush("for else:")

for limit in (5, 1):
    countdown = 3
    while countdown:
        countdown -= 1
        if countdown == limit:
            note("break", countdown)
            break
        note("tick", countdown)
    else:
        note("while else", countdown)
attempts = 0
while True:
    attempts += 1
    if attempts % 2:
        continue
    if attempts > 4:
        break
    note("even", attempts)
flush("while:")
