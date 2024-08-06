# Copyright (c) 2016 Universidade Federal Fluminense (UFF)
# Copyright (c) 2016 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""Definition Diff Object"""
from __future__ import (absolute_import, print_function,
                        division, unicode_literals)

from collections import OrderedDict

from future.utils import viewkeys

from ..persistence.models.base import Model, proxy_gen
from .definition import Definition
from .graphs.definition_diff_graph import DefinitionDiffGraph
from .diff import diff_dict, diff_set


class DefinitionDiff(Model):
    """This model represents a diff between two trials
    Initialize it by passing both trials ids:
        definition_diff = DefinitionDiff(1, 2)

    There are four visualization modes for the graph:
        tree: activation tree without any filters
            definition_diff.graph.mode = 0
        no match: tree transformed into a graph by the addition of sequence and
                  return edges and removal of intermediate call edges
            definition_diff.graph.mode = 1
        exact match: calls are only combined when all the sub-call match
            definition_diff.graph.mode = 2
        namesapce: calls are combined without considering the sub-calls
            definition_diff.graph.mode = 3


    You can change the graph width and height by the variables:
        definition_diff.graph.width = 600
        definition_diff.graph.height = 400
    """

    __modelname__ = "DefinitionDiff"

    DEFAULT = {
        "graph.width": 500,
        "graph.height": 500,
        "graph.mode": 3,
        "graph.time_limit": None,
    }

    REPLACE = {
        "graph_width": "graph.width",
        "graph_height": "graph.height",
        "graph_mode": "graph.mode",
        "graph_time_limit": "graph.time_limit",
    }

    def __init__(self, trial_ref1, trial_ref2, **kwargs):
        super(DefinitionDiff, self).__init__(trial_ref1, trial_ref2, **kwargs)
        self.definition1 = Definition(trial_ref1)
        self.definition2 = Definition(trial_ref2)

        self.graph = DefinitionDiffGraph(self)
        self.initialize_default(kwargs)

    @property
    def trial(self):
        """Return a tuple with information from both trials """
        extra = ("start", "finish", "duration_text", "code_hash")
        ignore = ("id",)
        return diff_dict(
            self.definition1.trial.to_dict(
                ignore=ignore, extra=extra),                     # pylint: disable=no-member
            self.definition2.trial.to_dict(ignore=ignore, extra=extra))                     # pylint: disable=no-member

    @property
    def modules(self):
        """Definition diff modules from trials"""
        return diff_set(
            set(proxy_gen(self.definition1.trial.modules)),
            set(proxy_gen(self.definition2.trial.modules)))

    @property
    def environment(self):
        """Definition diff environment variables"""
        return diff_set(
            set(self.definition1.trial.environment_attrs),
            set(self.definition2.trial.environment_attrs))

    @property
    def file_accesses(self):
        """Definition diff file accesses"""
        return diff_set(
            set(self.definition1.trial.file_accesses),
            set(self.definition2.trial.file_accesses),
            create_replaced=False)

    def _ipython_display_(self):
        """Display history graph"""
        if hasattr(self, "graph"):
            # pylint: disable=protected-access
            return self.graph._ipython_display_()
        from IPython.display import display
        display({
            'text/plain': 'Diff {}:{}'.format(
                self.definition1.trial.id,
                self.definition2.trial.id
            )
        })
