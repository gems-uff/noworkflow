# Copyright (c) 2016 Universidade Federal Fluminense (UFF)
# Copyright (c) 2016 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""Diff Object"""
from __future__ import (absolute_import, print_function,
                        division, unicode_literals)

from collections import OrderedDict

from future.utils import viewkeys

from .base import Model, proxy_gen
from .graphs.diff_graph import DiffGraph
from .trial import Trial


class Diff(Model):
    """This model represents a diff between two trials
    Initialize it by passing both trials ids:
        diff = Diff(2)

    There are four visualization modes for the graph:
        tree: activation tree without any filters
            diff.graph.mode = 0
        no match: tree transformed into a graph by the addition of sequence and
                  return edges and removal of intermediate call edges
            diff.graph.mode = 1
        exact match: calls are only combined when all the sub-call match
            diff.graph.mode = 2
        namesapce: calls are combined without considering the sub-calls
            diff.graph.mode = 3


    There are also three visualization modes for the diff:
        combine graphs: combines both trial graphs
            diff.graph.view = 0
        side by side: displays both graphs side by side
            diff.graph.view = 1
        combined and side by side: combine graphs and displays both separated
            diff.graph.view = 2


    You can change the graph width and height by the variables:
        diff.graph.width = 600
        diff.graph.height = 400
    """

    __modelname__ = "Diff"

    DEFAULT = {
        "graph.width": 500,
        "graph.height": 500,
        "graph.mode": 3,
        "graph.view": 0,
        "graph.neighborhoods": 3,
        "graph.time_limit": None,
    }

    REPLACE = {
        "graph_width": "graph.width",
        "graph_height": "graph.height",
        "graph_mode": "graph.mode",
        "graph_view": "graph.view",
        "graph_neighborhoods": "graph.neighborhoods",
        "graph_time_limit": "graph.time_limit",
    }

    def __init__(self, trial_ref1, trial_ref2, **kwargs):
        super(Diff, self).__init__(trial_ref1, trial_ref2, **kwargs)
        self.trial1 = Trial(trial_ref1)
        self.trial2 = Trial(trial_ref2)

        self.graph = DiffGraph(self)
        self.initialize_default(kwargs)

    @property
    def trial(self):
        """Return a tuple with information from both trials """
        extra = ("start", "finish", "duration_text")
        ignore = ("id",)
        return diff_dict(
            self.trial1.to_dict(ignore=ignore, extra=extra),                     # pylint: disable=no-member
            self.trial2.to_dict(ignore=ignore, extra=extra))                     # pylint: disable=no-member

    @property
    def modules(self):
        """Diff modules from trials"""
        return diff_set(
            set(proxy_gen(self.trial1.modules)),
            set(proxy_gen(self.trial2.modules)))

    @property
    def environment(self):
        """Diff environment variables"""
        return diff_set(
            set(self.trial1.environment_attrs),
            set(self.trial2.environment_attrs))

    @property
    def file_accesses(self):
        """Diff file accesses"""
        return diff_set(
            set(self.trial1.file_accesses),
            set(self.trial2.file_accesses),
            create_replaced=False)

    def _repr_html_(self):
        return self.graph._repr_html_()                                          # pylint: disable=protected-access


def diff_dict(before, after):
    """Compare dicts.
    Return a dict with keys shared by both dicts that have different values
        key -> [before[key], after[key]]
    """
    result = OrderedDict()
    for key in viewkeys(before):
        if key != "id" and before[key] != after[key]:
            result[key] = [before[key], after[key]]
    return result


def diff_set(before, after, create_replaced=True):
    """Compare sets to get additions, removals and replacements

    Return 3 sets:
    added -- objects present in second set, but not present in first set
    removed -- objects present in first set, but not present in second set
    replaced -- objects that have the same name in both sets, but are different
    """
    removed = before - after
    added = after - before
    replaced = set()

    removed_by_name = {}
    for element_removed in removed:
        removed_by_name[element_removed.name] = element_removed
    for element_added in added:
        element_removed = removed_by_name.get(element_added.name)
        if element_removed and create_replaced:
            replaced.add((element_removed, element_added))
    if create_replaced:
        for (element_removed, element_added) in replaced:
            removed.discard(element_removed)
            added.discard(element_added)

    return (added, removed, replaced)
