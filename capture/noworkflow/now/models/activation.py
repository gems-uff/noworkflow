# Copyright (c) 2014 Universidade Federal Fluminense (UFF)
# Copyright (c) 2014 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.

from __future__ import (absolute_import, print_function,
                        division, unicode_literals)

from collections import defaultdict
from sqlalchemy import Column, Integer, Text, TIMESTAMP
from sqlalchemy import ForeignKeyConstraint

from ..persistence import row_to_dict, persistence
from ..cross_version import lmap, items
from .model import Model


class Activation(Model, persistence.base):
    """Activation Table
    Store function activations from execution provenance
    """

    DEFAULT = {}
    REPLACE = {}

    __tablename__ = 'function_activation'
    __table_args__ = (
        ForeignKeyConstraint(['trial_id'], ['trial.id'], ondelete='CASCADE'),
        ForeignKeyConstraint(['caller_id'],
                             ['function_activation.id'], ondelete='CASCADE'),
        {'sqlite_autoincrement': True},
    )
    trial_id = Column(Integer, index=True)
    id = Column(Integer, primary_key=True)
    name = Column(Text)
    line = Column(Integer)
    _return = Column('return', Text)
    start = Column(TIMESTAMP)
    finish = Column(TIMESTAMP)
    caller_id = Column(Integer, index=True)

    def __getitem__(self, item):
        # ToDo: fix structures to use only getattr
        if item in ('start', 'finish'):
            return getattr(self, item)

    @property
    def objects(self):
        if not hasattr(self, '_objects'):
            self._types = defaultdict(list)
            self._objects = lmap(row_to_dict, persistence.load(
                'object_value', function_activation_id=self.id,
                trial_id=self.trial_id))

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
    def duration(self):
        return  int((self.finish - self.start).total_seconds() * 1000000)

    def show(self, _print=lambda x, offset=0: print):
        object_values = {'GLOBAL':[], 'ARGUMENT':[]}
        name = {'GLOBAL':'Globals', 'ARGUMENT':'Arguments'}
        for obj in self.objects:
            object_values[obj['type']].append(
                '{} = {}'.format(obj['name'], obj['value']))

        for typ, vals in items(object_values):
            if vals:
                _print('{type}: {values}'.format(type=name[typ],
                                                 values=', '.join(vals)))
        if self._return:
            _print('Return value: {ret}'.format(ret=self._return))

        if self.slicing_variables:
            _print('Variables:')
            for var in self.slicing_variables:
                _print('(L{line}, {name}, {value})'.format(**var), 1)

        if self.slicing_usages:
            _print('Usages:')
            for use in self.slicing_usages:
                _print('(L{line}, {name}, <{context}>)'.format(**use), 1)

        if self.slicing_dependencies:
            _print('Dependencies:')
            for dep in self.slicing_dependencies:
                _print(
                    ('(L{dependent[line]}, {dependent[name]}, {dependent[value]}) '
                    '<- (L{supplier[line]}, {supplier[name]}, {supplier[value]})'
                    ).format(**dep), 1)

    # ToDo: Improve hash
    def __hash__(self):
        return hash(self.id)

    def __eq__(self, other):
        return self.id == other.id
