"""Explicit lazy imports (PEP 810, 3.15): lazy import and lazy from ...
import, whose module runs only when a name is first used, after two plain
imports (#NEW:lazy-import-in-try, with #NEW:pyposast-lazy-import behind it)"""
import importlib
import sys

with open("lazy_target.py", "w", encoding="utf-8") as handle:
    handle.write("print('lazy_target runs')\nVALUE = 42\n")
importlib.invalidate_caches()

lazy import lazy_target
lazy from lazy_target import VALUE

print("before use", "lazy_target" in sys.modules)
print("value", VALUE)
print("module", lazy_target.VALUE)
