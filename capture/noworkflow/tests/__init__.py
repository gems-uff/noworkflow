# Copyright (c) 2016 Universidade Federal Fluminense (UFF)
# Copyright (c) 2016 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.

from __future__ import (absolute_import, print_function,
                        division, unicode_literals)

from ..now.persistence import persistence_config

persistence_config.mock()
persistence_config.connect(".")


from .prov_definition import TestSlicingDependencies
from .prov_execution import TestCallSlicing
from .prov_deployment import TestProvDeployment
from .cross_version_test import TestCrossVersion
from .formatter_test import TestFormatter
