"""The directories the program imports from (#419)

``sys.path`` decides what ``import`` finds: a program that imports a module
only when it is installed, or that lists its path, depends on it.
setuptools vendors packages in ``setuptools/_vendor``, which is not meant
to be on ``sys.path``.
"""
import sys

vendored = [entry for entry in sys.path
            if entry.replace("\\", "/").rstrip("/").endswith("setuptools/_vendor")]
print("setuptools/_vendor on sys.path:", len(vendored))
