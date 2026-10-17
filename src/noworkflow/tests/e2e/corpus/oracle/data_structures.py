"""Containers, comprehensions and slicing

Comprehensions of every kind (nested, filtered, over several iterables),
generator expressions consumed by builtins, slicing with negative steps,
slice assignment and deletion, ``sorted``/``reversed``/``enumerate``/
``zip``, ``map``/``filter`` and key functions, dict and set operations,
unpacking in ``for`` targets, starred targets nested in a tuple or made
of a tuple, starred names in list, tuple and set displays,
``collections``, ``heapq``, ``bisect`` and ``copy``. Python functions
called back by builtins are in callback_functions.py and callbacks.py, a
lambda inside a display or a comprehension in lambda_in_collection.py; a
dict display with ``**`` (#201 (PR), which needs JoaoFelipe/pyposast#2)
and a starred operand that is not a name, an attribute or a subscript are
left to the syntax corpus.
"""
import bisect
import collections
import copy
import heapq

grades = {"ana": [9, 7, 10], "bia": [6, 8], "caio": [10, 10, 9], "davi": []}
averages = {name: sum(marks) / len(marks) for name, marks in grades.items()
            if marks}
print(averages)
ranking = sorted(averages.items(), key=lambda item: -item[1])
print([name for name, average in ranking])
print({mark for marks in grades.values() for mark in marks if mark >= 9})
print([(row, col) for row in range(3) for col in range(row)])
print([[cell * row for cell in range(3)] for row in range(1, 3)])
print(sum(mark for marks in grades.values() for mark in marks),
      any(len(marks) > 2 for marks in grades.values()),
      all(grades.values()))
flat = [mark for marks in grades.values() for mark in marks]
print(flat, max(flat), min(flat), sorted(flat, reverse=True)[:3])

letters = list("abcdefghij")
print(letters[::2], letters[::-1], letters[-3:], letters[7:2:-2],
      letters[100:], letters[:-100])
letters[2:5] = ["X"]
print(letters)
letters[::3] = "123"
print(letters)
del letters[1::2]
print(letters)
letters[len(letters):] = ["end"]
letters[:0] = ["start"]
print(letters, "".join(reversed("stressed")))
matrix = [[1, 2, 3], [4, 5, 6]]
print([list(column) for column in zip(*matrix)], matrix[1][::-1])

for index, (name, marks) in enumerate(sorted(grades.items()), start=1):
    print(index, name, len(marks))
for (a, b), c in zip([(1, 2), (3, 4)], "xy"):
    print(a, b, c)
(first, *others), last = [1, 2, 3], 4
print(first, others, last)
head, *(second, third) = "xyz"
print(head, second, third)
evens, odds = [0, 2], [1, 3]
print([*evens, *odds], (*odds, *evens), sorted({*evens, *odds, *evens}))
print(list(map(str.upper, ["a", "b"])), list(filter(None, [0, 1, "", "x"])))
print(list(zip("abc", range(5))), list(enumerate("xy")))
print(sorted(["banana", "Apple", "cherry"], key=str.lower),
      sorted([(2, "b"), (1, "z"), (2, "a")]))

inventory = {"apple": 3}
inventory.setdefault("pear", 0)
inventory.update(kiwi=5, apple=4)
print(inventory.pop("pear"), inventory.get("plum", "none"), inventory)
merged = inventory | {"fig": 1}
merged |= {"kiwi": 0}
print(merged, list(merged.keys()), list(merged.values()))
odd, small = {1, 3, 5, 7}, {1, 2, 3}
print(odd & small, odd | small, odd - small, odd ^ small,
      small <= {1, 2, 3, 4}, frozenset(small) == small)

words = "the quick brown fox jumps over the lazy dog the end".split()
counts = collections.Counter(words)
print(counts.most_common(2), counts["the"], counts["cat"])
window = collections.deque(maxlen=3)
for word in words[:5]:
    window.append(word)
window.appendleft("first")
window.rotate(1)
print(list(window))
groups = collections.defaultdict(list)
for word in words:
    groups[len(word)].append(word)
print(sorted(groups.items()))
ordered = collections.OrderedDict.fromkeys("abc", 0)
ordered.move_to_end("a")
print(list(ordered))
Point = collections.namedtuple("Point", ["x", "y"], defaults=[0])
point = Point(3)
print(point, point._replace(y=4), point._asdict(), Point._fields)
chain = collections.ChainMap({"a": 1}, {"a": 2, "b": 3})
print(chain["a"], chain["b"], len(chain))

heap = []
for value in [5, 1, 8, 3, 9, 2]:
    heapq.heappush(heap, value)
print([heapq.heappop(heap) for _ in range(3)], heapq.nlargest(2, [5, 1, 8]))
ranks = [10, 20, 30, 40]
bisect.insort(ranks, 25)
print(ranks, bisect.bisect_left(ranks, 30), bisect.bisect(ranks, 5))

nested = {"list": [1, [2, 3]], "dict": {"k": [4]}}
shallow = copy.copy(nested)
deep = copy.deepcopy(nested)
nested["list"][1].append(99)
print(shallow["list"], deep["list"], shallow is nested, deep == nested)
stack = []
stack.append(1)
stack.extend([2, 3])
stack.insert(0, 0)
print(stack.pop(), stack.pop(0), stack, stack.index(2), stack.count(1))
print(tuple(range(3)) + (3,), (1, 2) * 2, [0] * 3, list(range(10, 0, -3)))
print(dict(zip("abc", range(3))), dict.fromkeys(range(2)), dict(**{"a": 1}))
