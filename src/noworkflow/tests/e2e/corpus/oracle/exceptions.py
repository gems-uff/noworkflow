"""Exceptions caught by the script

The order of ``try``/``except``/``else``/``finally``, ``raise ... from``
and the chained cause and context, re-raise, ``return`` through a
``finally``, a context manager whose ``__exit__`` suppresses (bound with
``as``: without it, see with_without_as.py), ``contextlib`` helpers,
exceptions raised inside generators, comprehensions and conditional
expressions, custom exception classes, ``assert``, ``break``/``continue``
inside ``try``, a bare ``except`` over an ordinary exception, and
``except*`` with exception groups. Only caught exceptions: an uncaught one
changes the exit status under ``now run`` (#226). The transformer does not
rewrite ``raise`` or ``assert`` yet, nor evaluate the types of ``except*``
(#77), so those statements compare plain Python with plain Python until it
does; the code around them and their handlers are traced.
Split out: an exception raised by the condition of a conditional
expression, or by its branches twice in one activation
(conditional_expression_errors.py), one caught inside a function that runs
in another call's arguments (exception_in_call_arguments.py), and one
raised by the first iterable of a generator expression
(genexp_iterable_raises.py), and one raised by the test of an ``if`` or a
``while`` statement (condition_test_errors.py). Under ``-cg``: #236
(``@contextlib.contextmanager``).
"""
import contextlib
import sys

trace = []


def parse(text):
    trace.append("parse " + text)
    try:
        value = int(text)
    except ValueError as error:
        trace.append("except")
        raise LookupError("bad number: " + text) from error
    else:
        trace.append("else")
        return value
    finally:
        trace.append("finally")


for text in ("12", "x1"):
    try:
        print("parsed", parse(text))
    except LookupError as error:
        print("caught", error, "| cause:", repr(error.__cause__),
              "| suppress context:", error.__suppress_context__)
print(trace)


def overriding():
    try:
        return "from try"
    finally:
        trace.append("cleanup ran")


def retrying():
    for attempt in range(3):
        try:
            if attempt < 2:
                raise RuntimeError("attempt %d" % attempt)
            return "succeeded at %d" % attempt
        except RuntimeError as error:
            trace.append(str(error))
        finally:
            trace.append("finally %d" % attempt)
    return "gave up"


trace.clear()
print(overriding(), retrying(), trace)


class ValidationError(Exception):
    def __init__(self, field, message):
        Exception.__init__(self, "{}: {}".format(field, message))
        self.field = field


class MissingField(ValidationError):
    pass


def validate(record):
    if "name" not in record:
        raise MissingField("name", "required")
    if not isinstance(record.get("age"), int):
        raise ValidationError("age", "must be an int")
    return True


for record in ({"name": "a", "age": 3}, {"age": 1}, {"name": "b"}):
    try:
        validate(record)
        print("valid", sorted(record))
    except MissingField as error:
        print("missing", error.field, error.args)
    except ValidationError as error:
        print("invalid", error)

try:
    try:
        {}["absent"]
    except KeyError:
        raise ValueError("while handling")
except ValueError as error:
    print("context:", repr(error.__context__), error.__cause__)

try:
    try:
        raise TypeError("inner")
    except TypeError:
        trace.append("re-raise")
        raise
except TypeError as error:
    print("re-raised", error, trace[-1])


class Suppress:
    def __init__(self, *kinds):
        self.kinds = kinds
        self.seen = []

    def __enter__(self):
        return self

    def __exit__(self, kind, value, traceback):
        self.seen.append(kind.__name__ if kind else None)
        return kind is not None and issubclass(kind, self.kinds)


guard = Suppress(ZeroDivisionError)
with guard as active:
    print(1 / 0)
with guard as active:
    print("no error inside")
print("after with", active.seen)
try:
    with Suppress(KeyError) as only_keys:
        raise IndexError("not suppressed")
except IndexError as error:
    print("escaped", error)

with contextlib.suppress(FileNotFoundError):
    open("does-not-exist.txt").read()
print("suppress done")


@contextlib.contextmanager
def tagged(name):
    trace.append("enter " + name)
    try:
        yield name.upper()
    except ArithmeticError as error:
        trace.append("handled " + type(error).__name__)
    finally:
        trace.append("exit " + name)


trace.clear()
with tagged("a") as upper:
    trace.append(upper)
with tagged("b") as upper:
    raise OverflowError("big")
print(trace)


def failing_generator():
    yield 1
    raise ValueError("generator failed")


values = []
try:
    for value in failing_generator():
        values.append(value)
except ValueError as error:
    print("from generator", values, error)

try:
    [1 / n for n in (1, 0)]
except ZeroDivisionError as error:
    print("from comprehension", error)

try:
    assert 1 + 1 == 3, "arithmetic is broken"
except AssertionError as error:
    print("assert", error)


def ratio(value, flag):
    return (10 // value) if flag else -1


for value, flag in ((5, True), (0, False), (0, True)):
    try:
        print("ratio", value, flag, ratio(value, flag))
    except ZeroDivisionError as error:
        print("ratio", value, flag, "raised", error)

try:
    int("not a number")
except:
    print("bare except caught", repr(sys.exc_info()[1]))

found = []
for number in range(10):
    try:
        if number % 2:
            continue
        if number > 6:
            break
        found.append(number)
    finally:
        trace.append(number)
print(found, trace[-3:])

try:
    raise ExceptionGroup("batch", [ValueError("v1"), TypeError("t1"),
                                   ValueError("v2")])
except* ValueError as group:
    print("values:", [str(error) for error in group.exceptions])
except* TypeError as group:
    print("types:", [str(error) for error in group.exceptions])

errors = []
for divisor in (2, 0, "x"):
    try:
        result = 10 / divisor
    except (ZeroDivisionError, TypeError) as error:
        errors.append(type(error).__name__)
    else:
        errors.append(result)
print(errors)
