# Copyright (c) 2015 Universidade Federal Fluminense (UFF)
# Copyright (c) 2015 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""Test now.cross_version module"""
from __future__ import (absolute_import, print_function,
                        division, unicode_literals)

import unittest
from ..now.utils.cross_version import bytes_string, cross_compile


class TestCrossVersion(unittest.TestCase):
    """TestCase for now.cross_version module"""

    def test_bytes_string_unicode_to_bytes(self):
        string = u"\u0435"
        self.assertEqual(1, len(string))
        self.assertEqual(2, len(bytes_string(string)))

    def test_bytes_string_bytes_to_bytes(self):
        string = b"a"
        self.assertEqual(1, len(string))
        self.assertEqual(1, len(bytes_string(string)))

    def test_cross_compile(self):
        code = b"a = 2"
        expected = compile(code, "name", "exec")
        result = cross_compile(code, "name", "exec")
        args = [
            "co_argcount", "co_cellvars", "co_code", "co_consts",
            "co_filename", "co_firstlineno", "co_freevars", "co_lnotab",
            "co_name", "co_names", "co_nlocals", "co_stacksize", "co_varnames"
        ]
        for arg in args:
            self.assertEqual(getattr(expected, arg), getattr(result, arg))
        # On Python 2: result.co_flags != expected.co_flags
