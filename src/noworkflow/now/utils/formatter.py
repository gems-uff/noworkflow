# Copyright (c) 2016 Universidade Federal Fluminense (UFF)
# Copyright (c) 2016 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""Define formatters for usual data structures to be used on IPython"""
from __future__ import (absolute_import, print_function,
                        division, unicode_literals)

from collections import Counter
from future.utils import lmap
from .cross_version import to_unicode


class PrettyStr(object):                                                         # pylint: disable=too-few-public-methods
    """Display lines with line breaks"""

    def _repr_pretty_(self, pretty, cycle):                                      # pylint: disable=unused-argument
        """Pretty repr for IPython"""
        pretty.text(str(self))


class PrettyLines(PrettyStr):                                                    # pylint: disable=too-few-public-methods
    """Display lines with line breaks


    Doctests:
    Print pretty lines:
    >>> plines = PrettyLines(["a", "b"])
    >>> print(str(plines))
    a
    b
    """

    def __init__(self, lines):
        """Constructor. lines must be a list of strings"""
        self.lines = lmap(to_unicode, lines)

    def append(self, element):
        """Append unicode element to list"""
        self.lines.append(to_unicode(element))

    def __str__(self):
        """Default str repr"""
        return "\n".join(self.lines)


class Table(list, PrettyStr):
    """Display tables


    Doctests:
    Print table
    >>> table = Table([["a", "bb"],["1", "2"],["3", "4"]])
    >>> print(str(table))
    a bb
    1  2
    3  4
    <BLANKLINE>

    Generate HTML:
    >>> print(table._repr_html_())  #doctest: +NORMALIZE_WHITESPACE
    <table>
      <tr><th>a</th><th>bb</th></tr>
      <tr><td>1</td><td>2</td></tr>
      <tr><td>3</td><td>4</td></tr>
    </table><br>

    Generate HTML without header:
    >>> table.show_header = False
    >>> print(table._repr_html_())  #doctest: +NORMALIZE_WHITESPACE
    <table>
      <tr><td>1</td><td>2</td></tr>
      <tr><td>3</td><td>4</td></tr>
    </table><br>

    Generate HTML when the table has no header
    >>> table.has_header = False
    >>> print(table._repr_html_())  #doctest: +NORMALIZE_WHITESPACE
    <table>
      <tr><td>a</td><td>bb</td></tr>
      <tr><td>1</td><td>2</td></tr>
      <tr><td>3</td><td>4</td></tr>
    </table><br>
    """

    def __init__(self, *args, **kwargs):
        args = list(args)
        if args and isinstance(args[0], list) and args[0]:
            if isinstance(args[0][0], list):
                args[0] = [lmap(to_unicode, x) for x in args[0]]
            else:
                args[0] = lmap(to_unicode, args[0])
        super(Table, self).__init__(*args, **kwargs)
        self.show_header = True
        self.has_header = True

    def _repr_html_(self):
        """HTML repr for IPython"""
        result = "<table>\n"
        try:
            iterator = iter(self)
            if self.has_header:
                header = next(iterator)
                if self.show_header:
                    result += "<tr>"
                    result += "".join("<th>{}</th>".format(x) for x in header)
                    result += "</tr>\n"
            for row in iterator:
                result += "<tr>"
                result += "".join("<td>{}</td>".format(x) for x in row)
                result += "</tr>\n"
        except StopIteration:
            pass
        result += "</table><br>"
        return result

    def __str__(self):
        """Default str repr"""
        size = Counter()
        for row in self:
            for i, value in enumerate(row):
                size[i] = max(size[i], len(str(value)))
        result = ""
        try:
            iterator = iter(self)
            if self.has_header:
                header = next(iterator)
                if self.show_header:
                    result += " ".join("{0:>{1}}".format(x, size[i])
                                       for i, x in enumerate(header))
                    result += "\n"
            for row in iterator:
                result += " ".join("{0:>{1}}".format(x, size[i])
                                   for i, x in enumerate(row))
                result += "\n"
        except StopIteration:
            pass
        return result
