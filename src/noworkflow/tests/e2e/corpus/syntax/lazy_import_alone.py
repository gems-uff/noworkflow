"""An explicit lazy import (PEP 810, 3.15) that is the only import statement
of the script, whose module runs only when its name is first used
(#NEW:lazy-import-in-try)"""
sys = __import__("sys")

with open("lazy_alone.py", "w", encoding="utf-8") as handle:
    handle.write("print('lazy_alone runs')\nVALUE = 7\n")
__import__("importlib").invalidate_caches()

lazy import lazy_alone

print("before use", "lazy_alone" in sys.modules)
print("value", lazy_alone.VALUE)
