# Copyright (c) 2019 Universidade Federal Fluminense (UFF)
# Copyright (c) 2019 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""Dataflow Model Object"""
from __future__ import (absolute_import, print_function,
                        division, unicode_literals)

import weakref


from ..persistence.models.base import Model

from .dependency_graph.dot_visitor import DotVisitor
from .dependency_graph.search_visitor import SearchEvaluationVisitor


class DataflowModel(Model):
    """Handle Dot export"""

    __modelname__ = "DataflowModel"

    def __init__(self, trial=None, activation=None):
        super(DataflowModel, self).__init__()
        self.trial = None
        if trial is not None:
            self.trial = weakref.proxy(trial)
        self.activation = None
        if activation is not None:
            self.activation = activation
        self.format = "svg"
        self.value_length = 0
        self.name_length = 55
        self.fallback = None
        self.run = True

    def _load_trial_and_activation(self):
        """Load trial or activation from trial/activation attributes"""
        if self.activation is None and self.trial is None:
            raise ValueError("Either activation or trial should be defined")
        elif self.activation is not None:
            self.trial = weakref.proxy(self.activation.trial)
        elif self.trial is not None:
            self.activation = self.trial.initial_activation

    def export_text(self):
        """Export facts from trial as text"""
        self._load_trial_and_activation()
        clusterizer = self.trial.dependency_clusterizer
        if self.run:
            clusterizer.run()
        visitor = DotVisitor(clusterizer, self.name_length, self.value_length)
        search = SearchEvaluationVisitor(clusterizer, self.activation.id)
        node = search.visit(clusterizer)

        visitor.visit(node, initial=True)
        return "\n".join(visitor.result)

    def _ipython_display_(self):
        from IPython import get_ipython
        from IPython.display import display
        ipython = get_ipython()
        obj = ipython.run_cell_magic(
            "dot", "--format {}".format(self.format), self.export_text()
        )
        display(obj)
