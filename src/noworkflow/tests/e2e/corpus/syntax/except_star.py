"""except* over an exception group (PEP 654, TryStar)"""


def fail():
    raise ExceptionGroup(
        "several", [ValueError("v"), TypeError("t"), KeyError("k")])


try:
    fail()
except* ValueError as group:
    print("value errors", [str(error) for error in group.exceptions])
except* (TypeError, KeyError) as group:
    print("other errors",
          sorted(type(error).__name__ for error in group.exceptions))
finally:
    print("finally")
print("after")
