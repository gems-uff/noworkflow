# Copyright (c) 2015 Universidade Federal Fluminense (UFF)
# Copyright (c) 2015 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""Test now.prov_deployment module"""
from __future__ import (absolute_import, print_function,
                        division, unicode_literals)

import unittest
import modulefinder
import platform
import os
from ..now.persistence import persistence
from ..now.prov_deployment import collect_environment_provenance
from ..now.prov_deployment import collect_modules_provenance
from ..now.prov_deployment import get_version
from . import mock

persistence = mock.Mock()


class TestProvDeployment(unittest.TestCase):
    """TestCase for now.prov_deployment module"""

    def test_collect_environment_provenance(self):
        env = collect_environment_provenance()
        self.assertIn('PWD', env)
        self.assertIn('PYTHON_VERSION', env)
        self.assertIn('PYTHON_IMPLEMENTATION', env)

    def _test_collect_modules_provenance(self):
        finder = modulefinder.ModuleFinder()
        finder.run_script(__file__)
        modules = collect_modules_provenance(finder.modules)
        modules = {m[0] for m in modules}
        self.assertIn('modulefinder', modules)

    def test_get_version_system_module(self):
        self.assertEqual(platform.python_version(), get_version('sys'))

    def test_get_version_distribution(self):
        self.assertEqual('1.0.2', get_version('pyposast'))

    def test_get_version_other(self):
        self.assertEqual(None, get_version('other'))
