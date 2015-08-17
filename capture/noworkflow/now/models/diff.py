# Copyright (c) 2015 Universidade Federal Fluminense (UFF)
# Copyright (c) 2015 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.

from __future__ import (absolute_import, print_function,
                        division, unicode_literals)

import time

from collections import namedtuple, OrderedDict, defaultdict

from ..utils import OrderedCounter, concat_iter, hashabledict
from ..cross_version import items, keys
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
        combined and side by side: combine graphs and displays both separated graphs
            diff.graph.view = 2


    You can change the graph width and height by the variables:
        diff.graph.width = 600
        diff.graph.height = 400
    """

    DEFAULT = {
        'graph.width': 500,
        'graph.height': 500,
        'graph.mode': 3,
        'graph.view': 0,
    }

    REPLACE = {
        'graph_width': 'graph.width',
        'graph_height': 'graph.height',
        'graph_mode': 'graph.mode',
        'graph_view': 'graph.view',
    }

    def __init__(self, trial_id1, trial_id2, exit=False, **kwargs):
        super(Diff, self).__init__(trial_id1, trial_id2, exit=exit, **kwargs)
        self.graph = DiffGraph(trial_id1, trial_id2)
        self.initialize_default(kwargs)

        self.trial1 = Trial(trial_id1, exit=exit)
        self.trial2 = Trial(trial_id2, exit=exit)

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

    def _repr_html_(self):
        return self.graph._repr_html_(self)


def dict_to_set(d):
    result = set()
    for key, value in items(d):
        result.add(activationdict({'name': key, 'value': value}))
    return result

def diff_dict(before, after):
    result = {}
    for key in keys(before):
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
