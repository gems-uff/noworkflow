# Copyright (c) 2016 Universidade Federal Fluminense (UFF)
# Copyright (c) 2016 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""Lightweight Module Dependency"""
from __future__ import (absolute_import, print_function,
                        division, unicode_literals)

from ..models import ModuleDependency
from .base import BaseLW, define_attrs


class ModuleDependencyLW(BaseLW):
    """Module Dependency lightweight object"""

    __slots__, attributes = define_attrs(
        ["trial_id", "module_id"], ["id"]
    )
    nullable = set()
    model = ModuleDependency

    def __init__(self, id_, module_id):
        self.trial_id = -1
        self.id = id_                                                            # pylint: disable=invalid-name
        self.module_id = module_id

    def is_complete(self):                                                       # pylint: disable=no-self-use
        """Module Dependency can always be removed from object store"""
        return True

    def __repr__(self):
        return ("ModuleDependency(module_id={})").format(self.module_id)
