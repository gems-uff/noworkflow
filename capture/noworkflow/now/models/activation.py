# Copyright (c) 2014 Universidade Federal Fluminense (UFF)
# Copyright (c) 2014 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.

from __future__ import (absolute_import, print_function,
                        division, unicode_literals)

from collections import defaultdict
from ..persistence import row_to_dict, persistence
from ..cross_version import lmap
from ..utils.data import HashableDict


class Activation(HashableDict):

    @property
    def objects(self):
        if not hasattr(self, '_objects'):
            self._types = defaultdict(list)
            self._objects = lmap(row_to_dict, persistence.load(
                'object_value', function_activation_id=self['id'],
                trial_id=self['trial_id']))

            for obj in self._objects:
                self._types[obj['type']].append(obj)
        return self._objects

    @property
    def types(self):
        self.objects
        return self._types

    @property
    def globals(self):
        return self.types['GLOBAL']

    @property
    def arguments(self):
        return self.types['ARGUMENT']
