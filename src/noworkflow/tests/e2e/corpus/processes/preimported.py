"""Imports of modules noWorkflow did and did not import before the script

The first line reports which of them were already in sys.modules when the
script started, the precondition of what the store records for them.
"""
import sys

print(sorted(name for name in ("json", "subprocess", "tabnanny")
             if name in sys.modules))
import json
import subprocess
import tabnanny
