# Copyright (c) 2014 Universidade Federal Fluminense (UFF)
# Copyright (c) 2014 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.

from __future__ import (absolute_import, print_function,
                        division, unicode_literals)

from ..persistence import row_to_dict, persistence

class Activation(dict):

    def el(self, e):
        if isinstance(e, dict):
            return Activation(e)
        else:
            return e

    def __key(self):
        return tuple((k,self.el(self[k])) for k in sorted(self))
    def __hash__(self):
        return hash(self.__key())
    def __eq__(self, other):
        return self.__key() == other.__key()

    def objects(self):
        return map(row_to_dict, persistence.load(
            'object_value', function_activation_id=self['id']))
