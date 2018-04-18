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

loader = unittest.TestLoader()
doctests = unittest.TestSuite()
for name, module in viewitems(tests_modules):
    model_test = doctest.DocTestSuite(
        sys.modules[module],
        optionflags=doctest.REPORT_ONLY_FIRST_FAILURE)
    locals()[name] = model_test
    doctests.addTests(model_test)

definition = unittest.TestSuite()
definition.addTests(loader.loadTestsFromTestCase(TestCodeBlockDefinition))
definition.addTests(loader.loadTestsFromTestCase(TestCodeComponentDefinition))
definition.addTests(loader.loadTestsFromTestCase(TestReconstruction))

execution = unittest.TestSuite()
execution.addTests(loader.loadTestsFromTestCase(TestScript))
execution.addTests(loader.loadTestsFromTestCase(TestStmtExecution))
execution.addTests(loader.loadTestsFromTestCase(TestExprExecution))
execution.addTests(loader.loadTestsFromTestCase(TestDepthExecution))

collection = unittest.TestSuite()
collection.addTests(definition)
collection.addTests(execution)

dataflow = unittest.TestSuite()
dataflow.addTests(loader.loadTestsFromTestCase(TestClusterizer))
dataflow.addTests(loader.loadTestsFromTestCase(TestDependencyClusterizer))
dataflow.addTests(loader.loadTestsFromTestCase(TestActivationClusterizer))
dataflow.addTests(loader.loadTestsFromTestCase(TestProspectiveClusterizer))
dataflow.addTests(loader.loadTestsFromTestCase(TestClusterizerConfig))


def load_tests(loader, tests, pattern):
    """Create test suite"""
    # pylint: disable=unused-argument
    suite = unittest.TestSuite()
    suite.addTests(doctests)
    suite.addTests(collection)
    suite.addTests(dataflow)
    suite.addTests(loader.loadTestsFromTestCase(TestCrossVersion))
    return suite
