"""except with several types and no parentheses (PEP 758, 3.14)"""
import sys

for text in ("x", None):
    try:
        int(text)
    except ValueError, TypeError:
        caught = sys.exception()
        print("caught", type(caught).__name__, caught)
