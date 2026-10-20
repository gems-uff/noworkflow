# Copyright (c) 2019 Universidade Federal Fluminense (UFF)
# Copyright (c) 2019 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""Dataflow Model Object"""
from __future__ import absolute_import, division, print_function, unicode_literals

from ..persistence.models.base import Model
from .dependency_graph.dot_visitor import DotVisitor
from .dependency_graph.search_visitor import SearchEvaluationVisitor


class DataflowModel(Model):
    """Handle Dot export

    Draws the dataflow of a trial, or only the part under one of its
    activations. The trial is held by a strong reference, so a model kept
    without its trial (``Trial().dot`` in a notebook) still draws it with
    the configuration chosen for it; the garbage collector frees the cycle
    with the trial once neither is reachable.
    """

    __modelname__ = "DataflowModel"

    def __init__(self, trial=None, activation=None):
        super(DataflowModel, self).__init__()
        if trial is None and activation is not None:
            trial = activation.trial
        self.trial = trial
        self.activation = activation
        self.format = "svg"
        self.value_length = 0
        self.name_length = 55
        self.fallback = None
        self.run = True

    def _load_trial_and_activation(self):
        """Return the trial and the activation where the drawing starts:
        the given activation, or the initial activation of the trial"""
        if self.trial is None:
            raise ValueError("Either activation or trial should be defined")
        activation = self.activation
        if activation is None:
            activation = self.trial.initial_activation
        return self.trial, activation

    def export_text(self):
        """Export facts from trial as text"""
        trial, activation = self._load_trial_and_activation()
        clusterizer = trial.dependency_clusterizer
        if self.run:
            clusterizer.run()
        visitor = DotVisitor(clusterizer, self.name_length, self.value_length)
        search = SearchEvaluationVisitor(clusterizer, activation.id)
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
