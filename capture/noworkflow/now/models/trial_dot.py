# Copyright (c) 2016 Universidade Federal Fluminense (UFF)
# Copyright (c) 2016 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""Trial Dot Object"""
from __future__ import (absolute_import, print_function,
                        division, unicode_literals)

import weakref


from ..persistence.models.base import Model

from .dependency_graph.dot_visitor import DotVisitor


class TrialDot(Model):
    """Handle Dot export"""

    __modelname__ = "TrialDot"

    def __init__(self, trial):
        super(TrialDot, self).__init__()
        self.trial = weakref.proxy(trial)
        self.format = "svg"
        self.value_length = 0
        self.name_length = 55
        self.fallback = None
        self.run = True

    def export_text(self):
        """Export facts from trial as text"""
        clusterizer = self.trial.dependency_clusterizer
        if self.run:
            clusterizer.run()
        visitor = DotVisitor(clusterizer, self.name_length, self.value_length)
        visitor.visit(clusterizer)
        return "\n".join(visitor.result)

    def _repr_svg_(self):
        if self.format == "svg":
            ipython = get_ipython()  # pylint: disable=undefined-variable
            return ipython.run_cell_magic(
                "dot", "--format {}".format(self.format), self.export_text()
            )

    def _repr_png_(self):
        if self.format == "png":
            ipython = get_ipython()  # pylint: disable=undefined-variable
            return ipython.run_cell_magic(
                "dot", "--format {}".format(self.format), self.export_text()
            )
