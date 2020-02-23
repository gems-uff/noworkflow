# Copyright (c) 2016 Universidade Federal Fluminense (UFF)
# Copyright (c) 2016 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""Lightweight Experiment"""
from __future__ import (absolute_import, print_function,
                        division, unicode_literals)
from .base import BaseLW, define_attrs


class ExperimentLW(BaseLW):                                                      # pylint: disable=too-many-instance-attributes
    """Evaluation lightweight object"""

    __slots__, attributes = define_attrs(
        ["description","name", "id"]
    )

    def __init__(self, name, id,description):
        self.description = description
        self.name = name
        self.id = id
    
    def __json__(self):
        return {
            'description': self.description,
            'name': self.name,
            'id': self.id
        }
