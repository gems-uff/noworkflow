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
from .graphs.dependency_graph import ActivationCluster


CALL_SCHEMA = "#3A85B9", "box", "black"
VAR_SCHEMA = "#85CBD0", "ellipse", "black"
FILE_SCHEMA = "white", "ellipse", "black"
BLACKBOX_SCHEMA = "black", "box", "grey"
GRAYBOX_SCHEMA = "grey", "box", "black"
IMPORT_SCHEMA = "#1B2881", "box", "#7AC5F9"


TYPES = {
    "call": CALL_SCHEMA,
    "normal": VAR_SCHEMA,
    "virtual": VAR_SCHEMA,
    "param": VAR_SCHEMA,
    "import": IMPORT_SCHEMA,
    "--blackbox--": BLACKBOX_SCHEMA,
    "--graybox--": GRAYBOX_SCHEMA,
}


def escape(string, size=55):
    """Escape string for dot file"""
    if not size:
        return ""
    if len(string) > size:
        half_size = (size - 5) // 2
        string = string[:half_size] + " ... " + string[-half_size:]
    return "" if string is None else string.replace('"', '\\"')


class TrialDot(Model):                                                           # pylint: disable=too-many-instance-attributes
    """Handle Dot export"""

    __modelname__ = "TrialDot"

    def __init__(self, trial):
        super(TrialDot, self).__init__()
        self.trial = weakref.proxy(trial)
        self.filter = DependencyFilter(trial)
        self.format = "svg"
        self.value_length = 0
        self.name_length = 55
        self.fallback = None
        self.run = True

    def dependency_filter_to_dot(self, cluster, result=None):
        """Create dot result"""
        if result is None:
            result = []
        if cluster.activation_id == -1:
            result.append("digraph dependency {")
            result.append("    rankdir=RL;")
            result.append("    node[fontsize=20]")
            self._add_components(cluster, result)
            self._set_rank(cluster, result)
            self._add_dependencies(result)
            result.append("}")
        else:
            result.append(
                "    " * (cluster.depth - 1) +
                "subgraph cluster_{}  {{".format(cluster.activation_id)
            )
            result.append("    " * cluster.depth + 'color="#3A85B9";')
            result.append("    " * cluster.depth + 'fontsize=30;')
            result.append("    " * cluster.depth +
                          'label = "{}";'.format(cluster.name))
            self._add_components(cluster, result)
            self._set_rank(cluster, result)
            result.append("    " * (cluster.depth - 1) + "}")
        return result

    def _add_components(self, cluster, result):
        """Add components to graph"""
        for component in cluster.components:
            if isinstance(component, ActivationCluster):
                self.dependency_filter_to_dot(
                    component, result=result
                )
            elif variable_id(component) in self.filter.filtered_variables:
                self._add_variable(
                    component, cluster.depth, self.schema_config(component),
                    result=result
                )

    def _add_variable(self, variable, depth, config, result):
        """Create variable for graph
        Arguments:
        variable -- Variable or FileAccesss object
        depth -- depth for configuring spaces in subclusters
        config -- color schema
        """
        color, shape, font = config
        var = variable_id(variable)

        value = escape(variable.value, self.value_length)
        name = escape(variable.name, self.name_length)

        if value == "now(n/a)":
            value = ""

        label_list = []
        if variable.line:
            label_list.append("{} ".format(variable.line))
        label_list.append(name)
        if value:
            label_list.append("\n{}".format(value))
        label = "".join(label_list)

        result.append("    " * depth + (
            '{var} '
            '[label="{label}"'
            ' fillcolor="{color}" fontcolor="{font}"'
            ' shape="{shape}"'
            ' style="filled"];'
        ).format(var=var, label=label, color=color, font=font, shape=shape))

    def _set_rank(self, cluster, result):
        """Set rank of variables"""
        for variables in cluster.same_rank:
            variables = [variable_id(var) for var in variables
                         if variable_id(var) in self.filter.filtered_variables]
            if variables:
                result.append(
                    "    " * cluster.depth +
                    "{rank=same " + " ".join(variables) + "}")

    def _add_dependencies(self, result):
        """Create dependencies"""
        filtered_variables = self.filter.filtered_variables
        for (source, target), style in viewitems(self.filter.dependencies):
            if source in filtered_variables and target in filtered_variables:
                result.append(('    {} -> {} [style="{}"];').format(
                    source, target, style
                ))

    def schema_config(self, variable):
        """Return color schema for variable
        or fallback if there is no valid schema
        """
        if isinstance(variable, FileAccess):
            return FILE_SCHEMA
        return TYPES.get(variable.type) or self.fallback

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
        if self.run:
            self.filter.run()
        getattr(self, self.trial.dependency_config.mode)()
        return "\n".join(
            self.dependency_filter_to_dot(self.filter.main_cluster)
        )

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
