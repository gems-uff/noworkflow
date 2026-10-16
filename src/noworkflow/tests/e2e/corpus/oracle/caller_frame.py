"""Builtins that read the namespace of their caller (#NEW:caller-frame)

A small calculator and report: ``eval`` and ``exec`` without explicit
namespaces, ``globals()`` used as a dispatch table, ``locals()`` and
``vars()`` used for string formatting, ``dir()`` without arguments,
``sys._getframe``, and a warning attributed to its caller by
``stacklevel``. Each of them looks at the frame that called it. Each step
runs in its own ``try`` and prints its result or the exception it raised,
so that every one of them shows.
"""
import os
import sys
import warnings

TAX = 0.25
price = 80


def apply_tax(amount):
    return amount * (1 + TAX)


def report(item, amount):
    total = apply_tax(amount)
    return "{item}: {amount} -> {total:.2f}".format_map(locals())


def summary(item):
    count = 3
    return "%(item)s x%(count)d" % vars()


def deprecated_total(amount):
    warnings.warn("use apply_tax", DeprecationWarning, stacklevel=2)
    return apply_tax(amount)


def failed(step, error):
    print(step, "failed:", type(error).__name__, error)


try:
    print("eval:", eval("price * 2 + TAX"))
except Exception as error:
    failed("eval", error)
try:
    exec("discount = price // 10")
    print("exec:", discount)  # bound by the exec above
except Exception as error:
    failed("exec", error)
try:
    print("globals:", globals()["apply_tax"](price))
except Exception as error:
    failed("globals", error)
try:
    print("locals:", report("lamp", price))
except Exception as error:
    failed("locals", error)
try:
    print("vars:", summary("lamp"))
except Exception as error:
    failed("vars", error)
try:
    print("dir:", [name for name in dir() if name in ("price", "report")])
except Exception as error:
    failed("dir", error)
try:
    print("frame:", sys._getframe().f_code.co_name)
except Exception as error:
    failed("frame", error)
try:
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        deprecated_total(4)
    print("warning from: {} line {}".format(
        os.path.basename(caught[0].filename), caught[0].lineno))
except Exception as error:
    failed("warning", error)
