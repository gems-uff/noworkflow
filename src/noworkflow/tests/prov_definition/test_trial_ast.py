# Copyright (c) 2026 Universidade Federal Fluminense (UFF)
# Copyright (c) 2026 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""Test TrialAst output helpers"""
from __future__ import (absolute_import, print_function,
                        division, unicode_literals)

import ast
import unittest

try:
    from unittest import mock
except ImportError:  # pragma: no cover
    import mock

from ...now.models.ast import trial_ast


class TestTrialAst(unittest.TestCase):
    """TestCase for TrialAst"""

    def test_construct_ast_uses_compatible_dump_on_python_38(self):
        """Do not pass indent to ast.dump on Python 3.8"""
        module = ast.parse("x = 1")
        trial_ast_instance = object.__new__(trial_ast.TrialAst)

        with mock.patch.object(trial_ast.TrialAst, "__call__", return_value=module):
            with mock.patch.object(trial_ast.sys, "version_info", (3, 8, 0)):
                with mock.patch.object(trial_ast.ast, "parse", return_value=module):
                    with mock.patch.object(trial_ast.ast, "dump") as dump:
                        dump.return_value = "Module(...)"
                        trial_ast_instance.construct_ast()

        dump.assert_called_once_with(module)

    def test_construct_ast_keeps_indented_dump_when_supported(self):
        """Pass indent to ast.dump on Python 3.9+"""
        module = ast.parse("x = 1")
        trial_ast_instance = object.__new__(trial_ast.TrialAst)

        with mock.patch.object(trial_ast.TrialAst, "__call__", return_value=module):
            with mock.patch.object(trial_ast.sys, "version_info", (3, 9, 0)):
                with mock.patch.object(trial_ast.ast, "parse", return_value=module):
                    with mock.patch.object(trial_ast.ast, "dump") as dump:
                        dump.return_value = "Module(...)"
                        trial_ast_instance.construct_ast()

        dump.assert_called_once_with(module, indent=2)
