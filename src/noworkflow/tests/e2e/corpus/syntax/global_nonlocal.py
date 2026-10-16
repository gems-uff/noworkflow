"""global and nonlocal declarations, each rebinding a name of an outer
scope"""

counter = 0


def increment():
    global counter
    counter += 1


def make_accumulator():
    total = 0

    def add(value):
        nonlocal total
        total += value
        return total
    return add


increment()
increment()
add = make_accumulator()
add(2)
print(counter, add(3))
