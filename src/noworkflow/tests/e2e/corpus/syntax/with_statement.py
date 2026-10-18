"""with statements: several items, parenthesized items, a tuple target, an
item without a target after a bound one, an exception received and
suppressed, and a file; what each target depends on is not checked, and a
with statement whose only item has no target is in with_no_target.py"""
import contextlib


class Managed:
    def __init__(self, name):
        self.name = name

    def __enter__(self):
        print("enter", self.name)
        return self.name.upper()

    def __exit__(self, *exc_info):
        print("exit", self.name)
        return False


class Reporting:
    def __enter__(self):
        return self

    def __exit__(self, kind, value, traceback):
        print("exit received", kind and kind.__name__, value)
        return True


class Pair:
    def __enter__(self):
        return 1, 2

    def __exit__(self, *exc_info):
        return False


with Managed("a") as first, Managed("b") as second, Managed("c"):
    print("inside", first, second)

with (
    Managed("d") as fourth,
    Managed("e"),
):
    print("parenthesized", fourth)

with Pair() as (left, right):
    print("pair", left, right)

with Managed("f") as sixth, Reporting():
    print("before raise", sixth)
    raise KeyError("swallowed")
print("after reporting")

with Reporting() as reporter:
    print("quiet", type(reporter).__name__)

with contextlib.suppress(ValueError):
    raise ValueError("ignored")
print("after suppress")

with open("with_output.txt", "w", encoding="utf-8") as handle:
    handle.write("written\n")
with open("with_output.txt", encoding="utf-8") as handle:
    print(handle.read().strip())
