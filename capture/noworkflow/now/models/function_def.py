# Copyright (c) 2016 Universidade Federal Fluminense (UFF)
# Copyright (c) 2016 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.

from __future__ import (absolute_import, print_function,
                        division, unicode_literals)

from sqlalchemy import Column, Integer, Text
from sqlalchemy import ForeignKeyConstraint

from collections import defaultdict
from ..persistence import row_to_dict, persistence
from ..cross_version import lmap
from ..utils import hashabledict
from .model import Model


class FunctionDef(Model, persistence.base):
    """Function Definition Table
    Store function definitions from the definion provenance
    """
    __tablename__ = 'function_def'
    __table_args__ = (
        ForeignKeyConstraint(['trial_id'], ['trial.id'], ondelete='CASCADE'),
        {'sqlite_autoincrement': True},
    )
    id = Column(Integer, primary_key=True)
    name = Column(Text)
    code_hash = Column(Text)
    trial_id = Column(Integer, index=True)

    DEFAULT = {}
    REPLACE = {}

    # ToDo: remove setitem and getitem
    def __setitem__(self, attr, value):
        setattr(self, attr, value)

    def __getitem__(self, attr):
        return getattr(self, attr)

    @property
    def objects(self):
        if not hasattr(self, '_objects'):
            self._types = defaultdict(list)
            self._objects = lmap(row_to_dict, persistence.load(
                'object', function_def_id=self['id']))

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

    @property
    def function_calls(self):
        return self.types['FUNCTION_CALL']
