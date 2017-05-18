# Copyright (c) 2016 Universidade Federal Fluminense (UFF)
# Copyright (c) 2016 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""Lightweight Evaluation"""
from __future__ import (absolute_import, print_function,
                        division, unicode_literals)

#from ..models import Evaluation
from .base import BaseLW, define_attrs


class ExceptionLW(BaseLW):                                                      # pylint: disable=too-many-instance-attributes
    """Evaluation lightweight object"""

    __slots__, attributes = define_attrs(
        ["trial_id", "id", "activation_id"],
        ["exception"]
    )
    nullable = set()
    #model = Evaluation

    def __init__(self, id_, trial_id, exception, activation_id):
        self.trial_id = trial_id
        self.id = id_                                                            # pylint: disable=invalid-name
        self.activation_id = activation_id
        self.exception = exception

    def is_complete(self):                                                       # pylint: disable=no-self-use
        """Evaluation can only be removed from object store
        if it has a moment
        """
        return True

    def __repr__(self):
        return (
            "Exception(id={0.id}, {0.exception})"
        ).format(self)
