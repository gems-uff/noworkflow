"""Exceptions raised by the test of an if or a while statement
(#NEW:condition-test-exception)

A reader of sensor readings that converts each reading in the test of the
statement that uses it, and catches the ``ValueError`` of a malformed
reading around that statement: the test of an ``if`` in a function, and
the test of a ``while`` at module level, on its third iteration. Each part
runs in its own ``try``, which reports an unexpected exception with the
function that raised it, so that both show. An exception raised by the
test of a conditional expression is in conditional_expression_errors.py.
"""
import traceback


def raised_in(error):
    """The name of the function where ``error`` was raised"""
    return traceback.extract_tb(error.__traceback__)[-1].name


def classify(reading):
    try:
        if float(reading) > 20.0:
            return "warm"
        return "cold"
    except ValueError:
        return "invalid"


try:
    print([classify("25.5"), classify("12"), classify("n/a")])
except Exception as error:
    print("classify stopped:", repr(error), "in", raised_in(error))

readings = ["7", "oops", "4", "9"]
count = 0
try:
    try:
        while int(readings.pop()) > 0:
            count += 1
    except ValueError:
        print("malformed reading after", count)
    print(count, readings)
except Exception as error:
    print("countdown stopped:", repr(error), "in", raised_in(error))
