"""Exceptions raised and re-raised inside the branches of an if
(#376)

A loader of settings that rejects a bad value by raising inside the
``elif`` and the ``else`` of an ``if``, and reports what each error was
raised while handling (its ``__context__``, None here); a lookup that,
inside an ``if`` in the handler of a missing key, logs the exception being
handled (``sys.exc_info()``) and re-raises it with a bare ``raise``; one
that raises its own error there, whose context is the missing key; and a
check whose bare ``raise``, inside an ``if``, runs where no exception is
being handled, which Python reports as a RuntimeError. Each part runs in
its own ``try``, which reports an unexpected exception by its type, so
that all of them show. An exception raised by the test of an ``if`` is in
condition_test_errors.py.
"""
import sys

settings = {"retries": "-1", "timeout": "0"}


def positive(name):
    value = int(settings[name])
    if value > 0:
        return value
    elif value == 0:
        raise ValueError("{} is zero".format(name))
    else:
        raise ValueError("{} is negative: {}".format(name, value))


for name in ("retries", "timeout"):
    try:
        positive(name)
    except ValueError as error:
        print("rejected:", error, "| context:", repr(error.__context__))
    except Exception as error:
        print("rejected", name, "unexpectedly:", type(error).__name__)


def lookup(name, required=True):
    try:
        return settings[name]
    except KeyError:
        if required:
            print("handling:", sys.exc_info()[0].__name__)
            raise
        return None


try:
    print("optional:", lookup("color", required=False))
    lookup("port")
except KeyError as error:
    print("re-raised:", type(error).__name__, error)
except Exception as error:
    print("re-raised unexpectedly:", type(error).__name__)


def extension(name):
    try:
        return settings[name]
    except KeyError:
        if name.startswith("x-"):
            raise LookupError("unknown extension " + name)
        raise


try:
    extension("x-debug")
except LookupError as error:
    print("replaced:", type(error).__name__, error,
          "| context:", type(error.__context__).__name__)


def require(name):
    # A bug: the bare raise was meant for a handler, and none is active.
    if name not in settings:
        raise
    return settings[name]


try:
    require("cache")
except RuntimeError as error:
    print("misplaced raise:", type(error).__name__, error)
except Exception as error:
    print("misplaced raise unexpectedly:", type(error).__name__)
