# Copyright (c) 2016 Universidade Federal Fluminense (UFF)
# Copyright (c) 2016 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""Trial Dot Object"""
from __future__ import (absolute_import, print_function,
                        division, unicode_literals)

import weakref

from ...utils.functions import resource

from .base import Model
from . import Activation, FileAccess
from . import SlicingVariable, SlicingUsage, SlicingDependency


RULES = "../resources/rules.pl"


class TrialDot(Model):
    """Handle Dot export"""

    __modelname__ = "TrialDot"

    def __init__(self, trial):
        super(TrialDot, self).__init__()
        self.trial = weakref.proxy(trial)


    def _export_text(self):
        result = []
        result.append("digraph dependency {")
        for variable in self.trial.slicing_variables:
            act_id = variable.activation_id
            act_id = "global" if act_id == -1 else act_id

            value = variable.value
            value = '' if value is None else value.replace('"', '\\"')

            name = variable.name
            name = '' if name is None else name.replace('"', '\\"')

            color, shape, fontcolor = "#85CBD0", "ellipse", "black"              # pylint: disable=unused-variable
            if name.startswith("iterator "):
                name = name[9:]
                color, shape, fontcolor = "#1B2881", "box", "#7AC5F9"
            if name.startswith("call "):
                name = name[5:]
                color, shape, fontcolor = "#3A85B9", "box", "black"
            result.append(('    v_{act_id}_{variable.id} '
                           '[label="{name}" fillcolor="{color}"'
                           ' fontcolor="{fontcolor}" shape="{shape}"'
                           ' style="filled"];').format(**locals()))
        result.append("")
        for dependency in self.trial.slicing_dependencies:
            dep_act_id = dependency.dependent_activation_id
            dep_act_id = "global" if dep_act_id == -1 else dep_act_id
            sup_act_id = dependency.supplier_activation_id
            sup_act_id = "global" if sup_act_id == -1 else sup_act_id

            result.append(('    v_{0}_{1} -> v_{2}_{3};').format(
                dep_act_id, dependency.dependent_id,
                sup_act_id, dependency.supplier_id
            ))
        result.append("}")
        return result

    def export_text(self):
        """Export facts from trial as text"""
        return "\n".join(self._export_text())

    def _repr_png_(self):
        ipython = get_ipython()
        return ipython.run_cell_magic('dot', '', self.export_text())
