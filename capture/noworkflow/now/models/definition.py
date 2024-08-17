# Copyright (c) 2016 Universidade Federal Fluminense (UFF)
# Copyright (c) 2016 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""Definition Object"""
from __future__ import (absolute_import, print_function,
                        division, unicode_literals)

from collections import OrderedDict

from future.utils import viewkeys

from ..persistence.models.base import Model, proxy_gen
from ..persistence.models.trial import Trial
from .graphs.definition_graph import DefinitionGraph, DefinitionAst


class Definition(Model):
    """This model represents a definition of trials
    Initialize it by passing a trials id:
        definition = Definition(1)

    There are one visualization modes for the graph:
        definition_tree: definition tree without any filters
            definition.graph.mode = 0


    You can change the graph width and height by the variables:
        definition.graph.width = 600
        definition.graph.height = 400
    """

    __modelname__ = "Definition"

    DEFAULT = {
        "graph.width": 500,
        "graph.height": 500,
        "graph.mode": 0
    }

    REPLACE = {
        "graph_width": "graph.width",
        "graph_height": "graph.height",
        "graph_mode": "graph.mode"
    }

    def __init__(self, trial_ref, **kwargs):
        super(Definition, self).__init__(trial_ref, **kwargs)
        self.trial = Trial(trial_ref)
        self.graph = DefinitionGraph(self)
        self.ast = DefinitionAst(self)
        self.initialize_default(kwargs)

    @property
    def modules(self):
        """Diff modules from trials"""
        return self.trial.modules

    @property
    def environment(self):
        """Diff environment variables"""
        return self.trial.environment_attrs

    @property
    def file_accesses(self):
        """Diff file accesses"""
        return self.trial.file_accesses

    def _ipython_display_(self):
        from IPython.display import display
        bundle = {
            'application/noworkflow.trial+json': self._modes[self.mode]()[1],
            'text/plain': 'Trial {}'.format(self.trial.id),
        }
        display(bundle, raw=True)
