# Copyright (c) 2016 Universidade Federal Fluminense (UFF)
# Copyright (c) 2016 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""Lightweight Activation"""
from __future__ import (absolute_import, print_function,
                        division, unicode_literals)
from ..models import Activation
from .base import BaseLW, define_attrs



class DepList(list):
    """Debug depa insertion"""
    # pylint: disable=E1003, E1101

    def pop(self, *args, **kwargs):
        """Pop"""
        import inspect
        result = super(DepList, self).pop(*args, **kwargs)
        print("pop", len(self), inspect.stack()[1][3])
        print(self)
        return result

    def append(self, *args, **kwargs):
        """Append"""
        import inspect
        super(DepList, self).append(*args, **kwargs)
        print("append", len(self), inspect.stack()[1][3])
        print(self)

    def insert(self, *args, **kwargs):
        """Insert"""
        import inspect
        super(DepList, self).insert(*args, **kwargs)
        print("insert", len(self), inspect.stack()[1][3])
        print(self)

DepList = list


class ActivationLW(BaseLW):
    """Activation lightweight object"""
    # pylint: disable=too-many-instance-attributes

    __slots__, attributes = define_attrs(
        ["trial_id", "id", "name", "start_checkpoint", "code_block_trial_id",
         "code_block_id"],
        ["file_accesses", "stage_tags", "context", "conditions", "permanent_conditions",
         "evaluation", "assignments", "closure", "func",
         "active", "depth", "parent", "generator", "last_activation", 
         "bound_dependency", "func_evaluation", "iscell"]
    )
    nullable = {"code_block_id"}
    model = Activation

    def __init__(self, evaluation, trial_id, name, start, code_block_id,id=None):
        # pylint: disable=too-many-arguments
        self.trial_id = trial_id
        self.id=id if id else  evaluation.id  # pylint: disable=invalid-name
        self.name = name
        self.start_checkpoint = start
        self.code_block_id = code_block_id if code_block_id else -1
        self.code_block_trial_id = trial_id

        self.evaluation = evaluation

        # Assignments
        self.assignments = []

        # Dependencies. Used to construct dependencies
        self.dependencies = DepList()

        # Variable context. Used in the slicing lookup
        self.context = {}
        # Closure activation
        self.closure = None
        # Parent activation
        self.parent = None
        self.last_activation = None
        # Executed function
        self.func = None

        # File accesses. Used to get the content after the activation
        self.file_accesses = []
        
        # Cells tags. Used to get the content after the activation
        self.stage_tagss = []

        # Track conditional dependencies
        self.conditions = []
        self.permanent_conditions = []

        # Active collection
        self.active = True

        # Current depth
        self.depth = 0

        # Generator Object
        self.generator = None

        # Method
        self.bound_dependency = None
        self.func_evaluation = None

        # Notebook
        self.iscell = False


    def is_complete(self):
        """Activation can always be removed from object store"""
        # pylint: disable=no-self-use
        return True

    def __repr__(self):
        return (
            "Activation(id={0.id}, name={0.name}, "
            "start_checkpoint={0.start_checkpoint}, "
            "code_block_id={0.code_block_id})"
        ).format(self)

    def __json__(self):
        return {
            'trial_id': self.trial_id,
            'id': self.id,
            'name': self.name,
            'start_checkpoint': self.start_checkpoint,
            'code_block_id': self.code_block_id
        }
