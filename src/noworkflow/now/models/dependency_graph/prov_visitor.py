# Copyright (c) 2017 Universidade Federal Fluminense (UFF)
# Copyright (c) 2017 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""Dot Cluster Visitor"""

from contextlib import contextmanager
from itertools import groupby
from collections import Counter

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


class ProvVisitor(ClusterVisitor):
    """Create dot file"""

    def __init__(self, clusterizer, name_length=55, value_length=55, create_activities=True):
        super(ProvVisitor, self).__init__(clusterizer)
        self.result = []
        self.indent = ""
        self.name_length = name_length
        self.value_length = value_length
        self.create_activities = create_activities
        self.activations_map = {}
        self.counter = Counter()

    def insert(self, text):
        """Insert indented line"""
        self.result.append("{}{}".format(self.indent, text))

    def process_cluster_content(self, cluster):
        """Process cluster content"""
        for node in cluster.elements:
            self.visit(node)

    def create_members(self, dependent, type_, group):
        """Create members in group"""
        for (dependent, dependency, style) in group:
            self.insert(
                'hadMember({}, {}, [type="version:{}", '
                'version:key="{}", version:checkpoint="{}"])'.format(
                    dependent, dependency,
                    style.get("_mode"), style.get("_key"),
                    style.get("_checkpoint")
                )
            )

    def create_dependency(self, dependent, type_, group):
        """Create dependencie for group"""
        existing_activity = self.activations_map.get(dependent)
        group = list(group)
        if existing_activity or self.create_activities:
            if not existing_activity:
                act_id = "{}_{}".format(type_, self.counter[type_])
                self.counter[type_] += 1
                g_id = "g_{}".format(self.counter["g"])
                self.counter["g"] += 1
                self.insert(
                    'activity({}, [type="script:operation"])'.format(
                        act_id
                    )
                )
                group = list(group)
                checkpoint = max(style.get("_checkpoint") for _, _, style in group)
                self.insert(
                    'wasGeneratedBy({}; {}, {}, -,[version:checkpoint="{}"])'.format(
                        g_id, dependent, act_id, checkpoint
                    )
                )
            else:
                act_id, g_id = existing_activity
            for (dependent, dependency, style) in group:
                #if not style.get("_checkpoint"):
                #    continue
                u_id = "u_{}".format(self.counter["u"])
                self.counter["u"] += 1
                attributes = []
                if style.get("_checkpoint"):
                    attributes.append('version:checkpoint="{}"'
                                      .format(style.get("_checkpoint")))
                self.insert(
                    'used({}; {}, {}, -,[{}])'.format(
                        u_id, act_id, dependency, ", ".join(attributes)
                    )
                )
                self.create_derivation(
                    dependent, dependency, style, act_id, g_id, u_id,
                )
        else:
            for (dependent, dependency, style) in group:
                self.create_derivation(dependent, dependency, style)

    def create_derivation(self, dependent, dependency, style, act_id="-", g_id="-", u_id="-"):
        """Create derivation"""
        # Todo: type_ == access should add extra attributes
        #if not style.get("_checkpoint"):
        #    return
        attributes = []
        if style.get("_checkpoint"):
            attributes.append('version:checkpoint="{}"'
                              .format(style.get("_checkpoint")))
        if style.get("_reference"):
            attributes.append('type="version:Reference"')
        self.insert(
            'wasDerivedFrom({}, {}, {}, {}, {}, [{}])'.format(
                dependent, dependency, act_id, g_id, u_id,
                ", ".join(attributes)
            )
        )

    def visit_initial(self, cluster):
        """Visit initial cluster"""
        self.indent = ""
        self.insert("prefix script <https://dew-uff.github.io/versioned-prov/ns/script#>")
        self.insert("prefix version <https://dew-uff.github.io/versioned-prov/ns#>")

        self.process_cluster_content(cluster)

        groups = groupby((
            (dependent, dependency, style)
            for (dependent, dependency), styles in viewitems(self.dependencies)
            for style in styles
        ), key=lambda x: (x[0], x[-1].get("_type")))
        for (dependent, type_), group in groups:
            if type_ == "member":
                self.create_members(dependent, type_, group)
            else:
                self.create_dependency(dependent, type_, group)

    def visit_cluster(self, cluster):
        """Visit other clusters"""
        self.visit_activation(cluster, name="return")
        self.process_cluster_content(cluster)

    def visit_evaluation(self, node):
        """Create evaluation node for graph"""
        name = escape(node.name, self.name_length)
        value = escape(node.value, self.value_length)

        self.insert(
            'entity({}, [value="{}", type="script:eval", '
            'script:line="{}", label="{}"])'.format(
                node.node_id, value, node.line, name
            )
        )

    def visit_activation(self, node, name=None):
        """Create activation node for graph"""
        name = escape(name or node.name, self.name_length)
        value = escape(node.value, self.value_length)
        self.insert(
            'entity({}, [value="{}", type="script:eval", '
            'script:line="{}", label="{}"])'.format(
                node.node_id, value, node.line, name
            )
        )
        act_id = "call_{}".format(node.node_id.split("_")[-1])
        g_id = "g_{}".format(self.counter["g"])
        self.counter["g"] += 1
        self.activations_map[node] = (act_id, g_id)

        self.insert(
            'activity({}, [type="script:call", label="{}"])'.format(
                act_id, node.activation_name
            )
        )
        self.insert(
            'wasGeneratedBy({}; {}, {}, -,[version:checkpoint="{}"])'.format(
                g_id, node.node_id, act_id, node.checkpoint
            )
        )

    def visit_access(self, node):
        """Create access node for graph"""
        label = escape(node.name, self.name_length)

        self.insert(
            'entity({}, [type="script:access", label="{}"])'.format(
                node.node_id, label
            )
        )
