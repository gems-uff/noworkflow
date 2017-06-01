# Copyright (c) 2017 Universidade Federal Fluminense (UFF)
# Copyright (c) 2017 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""Dot Cluster Visitor"""

from contextlib import contextmanager
from .base_visitor import ClusterVisitor
from .helpers import escape


class DotVisitor(ClusterVisitor):
    """Create dot file"""

    def __init__(self, fallback, name_length, value_length, types, dep_filter):  # pylint: disable=too-many-arguments
        super(DotVisitor, self).__init__(dep_filter)
        self.result = []
        self.name_length = name_length
        self.value_length = value_length
        self.fallback = fallback
        self.types = types
        self.indent = ""

    def insert(self, text):
        """Insert indented line"""
        self.result.append("{}{}".format(self.indent, text))

    @contextmanager
    def subgroup(self, title):
        """Create subgroup"""
        self.insert("{} {{".format(title))
        self.indent += "    "
        yield
        self.indent = self.indent[:4]
        self.insert("}")

    def process_cluster_content(self, cluster, ranks):
        """Process cluster content"""
        for component in cluster.components:
            self.visit(component)

        for rank in ranks:
            joined = " ".join(rank)
            if joined:
                self.insert("{{rank=same {}}}".format(joined))

    def visit_initial(self, node_id, cluster, ranks):
        """Visit initial cluster"""
        self.indent = ""
        with self.subgroup("digraph {}".format(node_id)):
            self.insert("rankdir=RL;")
            self.insert("node[fontsize=20]")

            self.process_cluster_content(cluster, ranks)

            for source, target, style in self.dependencies:
                self.insert("{} -> {} {};".format(source, target, style))

    def visit_cluster(self, node_id, cluster, ranks):
        """Visit other clusters"""
        with self.subgroup("subgraph {}".format(node_id)):
            self.insert('color="#3A85B9";')
            self.insert("fontsize=30;")
            self.insert('label = "{}";'.format(cluster.name))

            self.process_cluster_content(cluster, ranks)

    def visit_evaluation(self, node_id, element):
        """Create evaluation for graph
        Arguments:
        node_id -- node_id
        element -- evaluation object
        """

    def visit_variable(self, variable):
        """Create variable for graph
        Arguments:
        variable -- Variable or FileAccesss object
        depth -- depth for configuring spaces in subclusters
        config -- color schema
        """
        color, shape, font, style = self._schema_config(variable)
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
            label_list.append(" =\n{}".format(value))
        label = "".join(label_list)

        self.result.append("    " * self.depth + (
            '{var} '
            '[label="{label}"'
            ' fillcolor="{color}" fontcolor="{font}"'
            ' shape="{shape}"'
            ' style="{style}"];'
        ).format(
            var=var, label=label, color=color, font=font, shape=shape,
            style=style,
        ))

    def _schema_config(self, variable):
        """Return color schema for variable
        or fallback if there is no valid schema
        """
        if isinstance(variable, FileAccess):
            return self.types.get("access") or self.fallback
        return self.types.get(variable.type) or self.fallback