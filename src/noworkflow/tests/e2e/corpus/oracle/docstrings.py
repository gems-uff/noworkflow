"""Inventory tool: lists, adds and removes items.

The module docstring is the description of the command line.
(#NEW:docstrings-lost) The docstrings of functions, classes and methods are
in function_docstrings.py.
"""
import argparse

parser = argparse.ArgumentParser(prog="inventory", description=__doc__)
print(parser.description.splitlines()[0])
