# Copyright (c) 2014 Universidade Federal Fluminense (UFF)
# Copyright (c) 2014 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.

from __future__ import (absolute_import, print_function,
                        division, unicode_literals)

from .prov_definition import TestSlicingDependencies
from .prov_execution import TestCallSlicing

__all__ = [
    b'TestSlicingDependencies',
    b'TestCallSlicing',
]