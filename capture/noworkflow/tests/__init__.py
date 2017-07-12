# Copyright (c) 2016 Universidade Federal Fluminense (UFF)
# Copyright (c) 2016 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""Load tests"""
# pylint: disable=invalid-name
# pylint: disable=wrong-import-position
from __future__ import (absolute_import, print_function,
                        division, unicode_literals)

import doctest
import unittest
import sys

from future.utils import viewitems

from ..now.persistence import persistence_config

persistence_config.mock()
persistence_config.connect(".")


#from .prov_deployment import TestProvDeployment
from .prov_definition import TestCodeBlockDefinition
from .prov_definition import TestCodeComponentDefinition
from .prov_definition import TestReconstruction
from .prov_execution import TestScript, TestStmtExecution, TestExprExecution
from .prov_execution import TestDepthExecution
from .dependency import TestClusterizer, TestClusterizerConfig
from .dependency import TestProspectiveClusterizer
from .dependency import TestActivationClusterizer, TestDependencyClusterizer
from .cross_version_test import TestCrossVersion

from ..now.persistence.models import ORDER
from ..now.utils import formatter
from ..now.utils import functions



tests_modules = {
    model.__name__: model.__module__ for model in ORDER
}

tests_modules["formatter"] = formatter.__name__
tests_modules["functions"] = functions.__name__

suites = []
for name, module in viewitems(tests_modules):
    model_test = doctest.DocTestSuite(
        sys.modules[module],
        optionflags=doctest.REPORT_ONLY_FIRST_FAILURE)
    locals()[name] = model_test
    suites.append(model_test)


def load_tests(loader, tests, pattern):
    """Create test suite"""
    # pylint: disable=unused-argument
    suite = unittest.TestSuite()
    for test_suite in suites:
        suite.addTest(test_suite)
    suite.addTests(loader.loadTestsFromTestCase(TestCrossVersion))
    suite.addTests(loader.loadTestsFromTestCase(TestCodeBlockDefinition))
    suite.addTests(loader.loadTestsFromTestCase(TestCodeComponentDefinition))
    suite.addTests(loader.loadTestsFromTestCase(TestReconstruction))
    suite.addTests(loader.loadTestsFromTestCase(TestScript))
    suite.addTests(loader.loadTestsFromTestCase(TestStmtExecution))
    suite.addTests(loader.loadTestsFromTestCase(TestExprExecution))
    suite.addTests(loader.loadTestsFromTestCase(TestDepthExecution))
    suite.addTests(loader.loadTestsFromTestCase(TestClusterizer))
    suite.addTests(loader.loadTestsFromTestCase(TestDependencyClusterizer))
    suite.addTests(loader.loadTestsFromTestCase(TestActivationClusterizer))
    suite.addTests(loader.loadTestsFromTestCase(TestProspectiveClusterizer))
    suite.addTests(loader.loadTestsFromTestCase(TestClusterizerConfig))
    return suite
