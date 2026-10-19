"""raise ... from ...: an explicit cause, and from None"""


def parse(text):
    try:
        return int(text)
    except ValueError as error:
        raise RuntimeError("bad input") from error


try:
    parse("x")
except RuntimeError as error:
    print(error, type(error.__cause__).__name__, error.__suppress_context__)

try:
    try:
        {}["missing"]
    except KeyError:
        raise LookupError("hidden") from None
except LookupError as error:
    print(error, error.__cause__, error.__suppress_context__)
