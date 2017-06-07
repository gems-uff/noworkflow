# Copyright (c) 2017 Universidade Federal Fluminense (UFF)
# Copyright (c) 2017 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""Dot Cluster Visitor"""

from contextlib import contextmanager

from future.utils import viewitems

from .base_visitor import ClusterVisitor
from .attributes import Attributes


def escape(string, size=55):
    """Escape string for dot file"""
    if not size or not string:
        return ""
    if len(string) > size:
        half_size = (size - 5) // 2
        string = string[:half_size] + " ... " + string[-half_size:]
    return "" if string is None else string.replace('"', '\\"')


class DotVisitor(ClusterVisitor):
    """Create dot file"""

    def __init__(self, clusterizer, name_length=55, value_length=55):
        super(DotVisitor, self).__init__(clusterizer)
        self.result = []
        self.indent = ""
        self.name_length = name_length
        self.value_length = value_length

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

    def process_cluster_content(self, cluster):
        """Process cluster content"""
        for node in cluster.elements:
            self.visit(node)

        for rank in cluster.ranks:
            joined = " ".join(x.node_id for x in rank)
            if joined:
                self.insert("{{rank=same {}}}".format(joined))

    def visit_initial(self, cluster):
        """Visit initial cluster"""
        self.indent = ""
        with self.subgroup("digraph {}".format(cluster.node_id)):
            self.insert("rankdir=RL;")
            self.insert("node[fontsize=20]")

            self.process_cluster_content(cluster)

            for (source, target), style in viewitems(self.dependencies):
                self.insert("{} -> {} {};".format(source, target, style))

    def visit_cluster(self, cluster):
        """Visit other clusters"""
        with self.subgroup("subgraph {}".format(cluster.cluster_id)):
            self.insert('color="#3A85B9";')
            self.insert("fontsize=30;")
            self.insert('label = "{}";'.format(cluster.activation_name))

            self.visit_activation(cluster, name="return")
            self.process_cluster_content(cluster)

    def visit_evaluation(self, node):
        """Create evaluation node for graph"""
        name = escape(node.name, self.name_length)
        value = escape(node.value, self.value_length)

        label_list = ["{} {}".format(node.line, name)]
        if value:
            label_list.append(" =\n{}".format(value))
        label = "".join(label_list)

        attrs = Attributes({
            "label": label,
            "fillcolor": "#85CBD0",
            "fontcolor": "black",
            "shape": "box",
            "style": "rounded,filled",
        })
        self.insert("{} {};".format(node.node_id, attrs))

    def visit_activation(self, node, name=None):
        """Create activation node for graph"""
        name = escape(name or node.name, self.name_length)
        value = escape(node.value, self.value_length)

        label_list = ["{} {}".format(node.line, name)]
        if value:
            label_list.append(" =\n{}".format(value))
        label = "".join(label_list)

        attrs = Attributes({
            "label": label,
            "fillcolor": "#3A85B9",
            "fontcolor": "white",
            "shape": "box",
            "style": "filled",
        })
        self.insert("{} {};".format(node.node_id, attrs))

    def visit_access(self, node):
        """Create access node for graph"""
        label = escape(node.name, self.name_length)

        attrs = Attributes({
            "label": label,
            "fillcolor": "white",
            "fontcolor": "black",
            "shape": "box",
            "style": "rounded,filled",
        })
        self.insert("{} {};".format(node.node_id, attrs))

    def visit_value(self, node):
        """Create value node for graph"""
        label = escape(node.name, self.name_length)

        attrs = Attributes({
            "label": label,
            "fillcolor": "white",
            "fontcolor": "blue",
            "shape": "box",
            "style": "rounded,filled",
        })
        self.insert("{} {};".format(node.node_id, attrs))
