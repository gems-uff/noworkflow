# Copyright (c) 2015 Universidade Federal Fluminense (UFF)
# Copyright (c) 2015 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.

from __future__ import (absolute_import, print_function,
                        division, unicode_literals)

import time

from collections import namedtuple, OrderedDict, defaultdict

from ..utils import OrderedCounter, concat_iter, hashabledict
from ..graphs.diff_graph import DiffGraph
from .model import Model
from .trial import Trial


class activationdict(dict):
    def __key(self):
        return tuple((k,self[k]) for k in sorted(self))
    def __hash__(self):
        return hash(self.__key())
    def __eq__(self, other):
        return self['name'] == other['name']


class fadict(dict):
    def __key(self):
        return (self['name'],
                self['content_hash_before'],
                self['content_hash_after'])
    def __hash__(self):
        return hash(self.__key())
    def __eq__(self, other):
        return ((self['content_hash_before'] == other['content_hash_before'])
            and (self['content_hash_after'] == other['content_hash_after']))


class Diff(Model):
    """ This model represents a diff between two trials
    Initialize it by passing both trials ids:
        diff = Diff(2)

    There are two visualization modes for the graph:
        exact match: calls are only combined when all the sub-call match
            diff.graph_type = 0
        combined: calls are combined without considering the sub-calls
            diff.graph_type = 1

    There are also three visualization modes for the diff:
        combine graphs: combines both trial graphs
            diff.display_mode = 0
        side by side: displays both graphs side by side
            diff.display_mode = 1
        combined and side by side: combine graphs and displays both separated graphs
            diff.display_mode = 2


    You can change the graph width and height by the variables:
        diff.graph_width = 600
        diff.graph_height = 400
    """

    DEFAULT = {
        'graph_width': 500,
        'graph_height': 500,
        'graph_type': 0,
        'display_mode': 0,
    }

    def __init__(self, trial_id1, trial_id2, exit=False, **kwargs):
        super(Diff, self).__init__(trial_id1, trial_id2, exit=exit, **kwargs)
        self.initialize_default(kwargs)

        self.trial1 = Trial(trial_id1, exit=exit)
        self.trial2 = Trial(trial_id2, exit=exit)
        self._graph_types = {
            0: self.independent_naive_activation_graph,
            1: self.combined_naive_activation_graph
        }
        self._display_modes = {
            0: "combined",
            1: "side by side",
            2: "both",
        }
        self._independent_cache = None
        self._combined_cache = None
        self.diff_graph = DiffGraph(trial_id1, trial_id2)


    def trial(self):
        """ Returns a tuple with the information of both trials """
        return diff_dict(self.trial1.info(), self.trial2.info())

    def modules(self):
        """ Diffs modules from trials """
        fn = lambda x: hashabledict(x)
        return diff_set(
            set(self.trial1.modules(fn)[1]),
            set(self.trial2.modules(fn)[1]))

    def environment(self):
        """ Diffs environment variables """
        return diff_set(
            dict_to_set(self.trial1.environment()),
            dict_to_set(self.trial2.environment()))

    def file_accesses(self):
        """ Diffs file accesses """
        return diff_set(
            set(fadict(fa) for fa in self.trial1.file_accesses()),
            set(fadict(fa) for fa in self.trial2.file_accesses()))

    def independent_naive_activation_graph(self):
        """ Generates an activation graph for both trials and transforms it into an
            exact match graph supported by d3 """
        return self.diff_graph.exact_match(self)
        if not self._independent_cache:
            g1 = self.trial1.independent_activation_graph()
            g2 = self.trial2.independent_activation_graph()
            self._independent_cache = NaiveGraphDiff(g1, g2).to_dict(), g1, g2
        return self._independent_cache

    def combined_naive_activation_graph(self):
        """ Generates an activation graph for both trials and transforms it into an
            combined graph supported by d3 """
        return self.diff_graph.combine(self)
        if not self._combined_cache:
            g1 = self.trial1.combined_activation_graph()
            g2 = self.trial2.combined_activation_graph()
            self._combined_cache = NaiveGraphDiff(g1, g2).to_dict(), g1, g2
        return self._combined_cache

    def _repr_html_(self):
        """ Displays d3 graph on ipython notebook """
        uid = str(int(time.time()*1000000))

        result = """
            <div class="nowip-diff" data-width="{width}"
                 data-height="{height}" data-uid="{uid}"
                 data-id1="{id1}" data-id2="{id2}" data-mode="{mode}">
                {data}
            </div>
        """.format(
            uid=uid, id1=self.trial1.id, id2=self.trial2.id,
            mode=self.display_mode,
            data=self.escape_json(self._graph_types[self.graph_type]()),
            width=self.graph_width, height=self.graph_height)
        return result


def dict_to_set(d):
    result = set()
    for key, value in d.items():
        result.add(activationdict({'name': key, 'value': value}))
    return result

def diff_dict(before, after):
    result = {}
    for key in before.keys():
        if key != 'id' and before[key] != after[key]:
            result[key] = [before[key], after[key]]
    return result

def diff_set(before, after):
    removed = before - after
    added = after - before
    replaced = set()

    removed_by_name = {}
    for element_removed in removed:
        removed_by_name[element_removed['name']] = element_removed
    for element_added in added:
        element_removed = removed_by_name.get(element_added['name'])
        if element_removed:
            replaced.add((element_removed, element_added))
    for (element_removed, element_added) in replaced:
        removed.discard(element_removed)
        added.discard(element_added)

    return (added, removed, replaced)

