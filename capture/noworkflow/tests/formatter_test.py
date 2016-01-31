# Copyright (c) 2015 Universidade Federal Fluminense (UFF)
# Copyright (c) 2015 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""Test now.formatter module"""
from __future__ import (absolute_import, print_function,
                        division, unicode_literals)

import unittest
from ..now.utils.formatter import PrettyLines, Table


class PrettyMock(object):

    def __init__(self):
        self.result = ""

    def text(self, t):
        self.result += t


class TestFormatter(unittest.TestCase):
    """TestCase for now.formatter module"""

    def test_pretty_lines_repr_pretty_(self):
        lines = ["a", "b"]
        pmock = PrettyMock()
        plines = PrettyLines(lines)
        plines._repr_pretty_(pmock, None)
        self.assertEqual("a\nb", pmock.result)

    def test_pretty_lines_str_(self):
        lines = ["a", "b"]
        plines = PrettyLines(lines)
        self.assertEqual("a\nb", str(plines))

    def test_table_repr_html_with_header(self):
        table = [["a", "b"], ["1", "2"]]
        table = Table(table)
        self.assertEqual(
            "<table>"
            "<tr><th>a</th><th>b</th></tr>"
            "<tr><td>1</td><td>2</td></tr>"
            "</table><br>",
            table._repr_html_()
        )

    def test_table_repr_html_without_header(self):
        table = [["a", "b"], ["1", "2"]]
        table = Table(table)
        table.has_header = False
        self.assertEqual(
            "<table>"
            "<tr><td>a</td><td>b</td></tr>"
            "<tr><td>1</td><td>2</td></tr>"
            "</table><br>",
            table._repr_html_()
        )

    def test_table_repr_html_skip_header(self):
        table = [["a", "b"], ["1", "2"]]
        table = Table(table)
        table.show_header = False
        self.assertEqual(
            "<table>"
            "<tr><td>1</td><td>2</td></tr>"
            "</table><br>",
            table._repr_html_()
        )

    def test_table_str_(self):
        table = [["a", "bb"], ["1", "2"]]
        table = Table(table)
        self.assertEqual("a bb\n1  2\n", str(table))
