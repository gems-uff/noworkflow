# Copyright (c) 2016 Universidade Federal Fluminense (UFF)
# Copyright (c) 2016 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.

from __future__ import (absolute_import, print_function,
                        division, unicode_literals)

import doctest
import unittest
import sys

from ..now.persistence import persistence_config

persistence_config.mock()
persistence_config.connect(".")


#from .prov_definition import TestDefinition
#from .prov_execution import TestCallSlicing
#from .prov_deployment import TestProvDeployment
from .cross_version_test import TestCrossVersion
from .formatter_test import TestFormatter

from ..now.persistence.models import ORDER


suites = []
for model in ORDER:
    model_test = doctest.DocTestSuite(sys.modules[model.__module__])
    locals()[model.__name__] = model_test
    suites.append(model_test)


def load_tests(loader, tests, pattern):
    suite = unittest.TestSuite()
    for test_suite in suites:
        suite.addTest(test_suite)
    suite.addTests(loader.loadTestsFromTestCase(TestCrossVersion))
    suite.addTests(loader.loadTestsFromTestCase(TestFormatter))
    return suite
