# Copyright (c) 2016 Universidade Federal Fluminense (UFF)
# Copyright (c) 2016 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""Test now.prov_deployment module"""
from __future__ import (absolute_import, print_function,
                        division, unicode_literals)

import unittest
import modulefinder
import platform
import os

from future.utils import viewvalues

from ..now.collection.metadata import Metascript


class TestProvDeployment(unittest.TestCase):
    """TestCase for now.prov_deployment module"""

    def test_collect_environment_provenance(self):
        meta = Metascript()
        meta.deployment._collect_environment_provenance(meta)
        env = {e.name:e.value
               for e in viewvalues(meta.environment_attrs_store.store)}
        self.assertIn("PWD", env)
        self.assertIn("PYTHON_VERSION", env)
        self.assertIn("PYTHON_IMPLEMENTATION", env)

    def _test_collect_modules_provenance(self):
        finder = modulefinder.ModuleFinder()
        finder.run_script(__file__)
        meta = Metascript()
        meta.deployment._collect_modules_provenance(meta, finder.modules)
        modules = {m.name
                   for m in viewvalues(meta.modules_store.store)}
        self.assertIn("modulefinder", modules)

    def test_get_version_system_module(self):
        meta = Metascript()
        self.assertEqual(
            platform.python_version(), meta.deployment._get_version("sys"))

    def test_get_version_distribution(self):
        meta = Metascript()
        self.assertEqual("1.1.0", meta.deployment._get_version("pyposast"))

    def test_get_version_other(self):
        meta = Metascript()
        self.assertEqual(None, meta.deployment._get_version("other"))
