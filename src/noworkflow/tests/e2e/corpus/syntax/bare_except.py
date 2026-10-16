"""A bare except catches every exception, the ones that derive from
BaseException only (SystemExit, KeyboardInterrupt) included
(#NEW:bare-except-narrowed)"""
import sys

try:
    sys.exit(3)
except:
    print("caught", sys.exc_info()[0].__name__)
try:
    raise KeyboardInterrupt
except:
    print("caught", sys.exc_info()[0].__name__)
print("done")
