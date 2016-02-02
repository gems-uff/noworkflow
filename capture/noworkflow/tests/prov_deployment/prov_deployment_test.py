# Copyright (c) 2016 Universidade Federal Fluminense (UFF)
# Copyright (c) 2016 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""Test now.prov_deployment module"""
from __future__ import (absolute_import, print_function,
                        division, unicode_literals)

import unittest
import platform

from future.utils import viewvalues

from ...now.collection.metadata import Metascript


NAME = "./noworkflow/tests/examples/script.py"
MODULES = "./noworkflow/tests/examples/modules.py"


class TestProvDeployment(unittest.TestCase):
    """TestCase for now.prov_deployment module"""

    def prepare(self, name=NAME):
        metascript = Metascript()
        metascript.path = name
        metascript.name = name
        metascript.verbose = True
        return metascript

    def test_collect_environment_provenance(self):
        metascript = self.prepare()
        metascript.deployment._collect_environment_provenance()
        env = {e.name: e.value
               for e in viewvalues(metascript.environment_attrs_store.store)}
        self.assertIn("PWD", env)
        self.assertIn("PYTHON_VERSION", env)
        self.assertIn("PYTHON_IMPLEMENTATION", env)

    def test_collect_modules_provenance(self):
        metascript = self.prepare(name=MODULES)
        metascript.deployment._collect_modules_provenance()
        modules = {m.name
                   for m in viewvalues(metascript.modules_store.store)}
        self.assertIn("ast", modules)
        self.assertIn("script", modules)

    def test_get_version_system_module(self):
        metascript = self.prepare()
        self.assertEqual(platform.python_version(),
                         metascript.deployment._get_version("sys"))

    def test_get_version_distribution(self):
        metascript = self.prepare()
        self.assertEqual("1.1.3",
                         metascript.deployment._get_version("pyposast"))

    def test_get_version_other(self):
        metascript = self.prepare()
        self.assertEqual(None, metascript.deployment._get_version("other"))
