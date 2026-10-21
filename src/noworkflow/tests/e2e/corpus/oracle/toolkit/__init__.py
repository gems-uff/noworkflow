"""Package imported by modules.py, open_wrapper_warning.py and
open_files_kept_alive.py: re-exports and package state"""
from .shapes import Circle, Square
from . import registry

VERSION = (1, 4)
__all__ = ["Circle", "Square", "registry", "describe"]


def describe(shape):
    return "{} with area {:.2f}".format(type(shape).__name__, shape.area())
