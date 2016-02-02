# Copyright (c) 2016 Universidade Federal Fluminense (UFF)
# Copyright (c) 2016 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""Define formatters for usual data structures to be used on IPython"""
from __future__ import (absolute_import, print_function,
                        division, unicode_literals)

from collections import Counter


class PrettyStr(object):                                                         # pylint: disable=too-few-public-methods
    """Display lines with line breaks"""

    def _repr_pretty_(self, pretty, cycle):                                      # pylint: disable=unused-argument
        """Pretty repr for IPython"""
        pretty.text(str(self))


class PrettyLines(PrettyStr):                                                    # pylint: disable=too-few-public-methods
    """Display lines with line breaks"""

    def __init__(self, lines):
        """Constructor. lines must be a list of strings"""
        self.lines = lines

    def __str__(self):
        """Default str repr"""
        return "\n".join(self.lines)


class Table(list, PrettyStr):
    """Display tables"""

    def __init__(self, *args, **kwargs):
        super(Table, self).__init__(*args, **kwargs)
        self.show_header = True
        self.has_header = True

    def _repr_html_(self):
        """HTML repr for IPython"""
        result = "<table>"
        try:
            iterator = iter(self)
            if self.has_header:
                header = next(iterator)
                if self.show_header:
                    result += "<tr>"
                    result += "".join("<th>{}</th>".format(x) for x in header)
                    result += "</tr>"
            for row in iterator:
                result += "<tr>"
                result += "".join("<td>{}</td>".format(x) for x in row)
                result += "</tr>"
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
