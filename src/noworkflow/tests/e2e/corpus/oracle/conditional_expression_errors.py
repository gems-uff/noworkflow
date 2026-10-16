"""Exceptions raised inside conditional expressions
(#NEW:conditional-expression-exception)

A grading helper whose conditional expressions divide by a count that can
be zero, and that catches the ``ZeroDivisionError`` where it handles the
input: raised by the condition in a function, and raised by a branch on
two iterations of a loop. Each part runs in its own ``try``, so that both
show. A single exception in a branch per function call is in
exceptions.py; one raised by the test of an ``if`` or a ``while``
statement, in condition_test_errors.py.
"""


def label(total, count):
    try:
        return "high" if total / count > 5 else "low"
    except ZeroDivisionError:
        return "no data"


try:
    labels = [label(30, 3), label(10, 5), label(10, 0)]
    print(labels)
except Exception as error:
    print("label failed:", repr(error))

averages = []
try:
    for total, count in ((10, 2), (10, 0), (0, 0), (0, 4)):
        try:
            average = total // count if total else -total // count
        except ZeroDivisionError:
            average = None
        averages.append(average)
    print(averages)
except Exception as error:
    print("averages failed:", repr(error), averages)
