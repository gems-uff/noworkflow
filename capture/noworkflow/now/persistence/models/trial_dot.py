# Copyright (c) 2016 Universidade Federal Fluminense (UFF)
# Copyright (c) 2016 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""Trial Dot Object"""
from __future__ import (absolute_import, print_function,
                        division, unicode_literals)

import weakref

from future.utils import viewitems

from .base import Model
from . import FileAccess
from .graphs.dependency_graph import DependencyFilter, variable_id
from .graphs.dependency_graph import DotVisitor


CALL_SCHEMA = "#3A85B9", "box", "white", "filled"
VAR_SCHEMA = "#85CBD0", "box", "black", "rounded,filled"
FILE_SCHEMA = "white", "box", "black", "rounded,filled"
BLACKBOX_SCHEMA = "black", "box", "grey", "filled"
GRAYBOX_SCHEMA = "grey", "box", "black", "filled"
IMPORT_SCHEMA = "#1B2881", "box", "#7AC5F9", "filled"


TYPES = {
    "call": CALL_SCHEMA,
    "normal": VAR_SCHEMA,
    "virtual": VAR_SCHEMA,
    "param": VAR_SCHEMA,
    "import": IMPORT_SCHEMA,
    "--blackbox--": BLACKBOX_SCHEMA,
    "--graybox--": GRAYBOX_SCHEMA,
    "access": FILE_SCHEMA,
}


class TrialDot(Model):                                                           # pylint: disable=too-many-instance-attributes
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


    def simulation(self):
        """Configure simulation graph"""
        self.fallback = None

    def prospective(self):
        """Configure prospective graph"""
        self.fallback = None

    def dependency(self):
        """Configure dependency graph"""
        self.fallback = VAR_SCHEMA

    def export_text(self):
        """Export facts from trial as text"""
        dep_filter = self.trial.dependency_filter
        if self.run:
            dep_filter.run()
        getattr(self, self.trial.dependency_config.mode)()
        visitor = DotVisitor(self.fallback, self.name_length,
                             self.value_length, TYPES, dep_filter)
        visitor.visit(dep_filter.main_cluster)
        return "\n".join(visitor.result)

    def _repr_svg_(self):
        if self.format == "svg":
            ipython = get_ipython()
            return ipython.run_cell_magic(
                "dot", "--format {}".format(self.format), self.export_text()
            )

    def _repr_png_(self):
        if self.format == "png":
            ipython = get_ipython()
            return ipython.run_cell_magic(
                "dot", "--format {}".format(self.format), self.export_text()
            )
