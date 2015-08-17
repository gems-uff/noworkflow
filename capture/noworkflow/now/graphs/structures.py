# Copyright (c) 2015 Universidade Federal Fluminense (UFF)
# Copyright (c) 2015 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.

from __future__ import (absolute_import, print_function,
                        division, unicode_literals)


import json
import traceback
import time
from datetime import datetime
from collections import OrderedDict
from ..utils import calculate_duration, FORMAT, OrderedCounter, print_msg
from ..cross_version import default_string, pickle, items, cvmap
from ..persistence import row_to_dict, persistence


class Graph(object):
    def escape_json(self, data):
        data = json.dumps(data)
        return (data.replace('&', '\\u0026')
                    .replace('<', '\\u003c')
                    .replace('>', '\\u003e'))


def prepare_cache(get_type):
    def cache(name, attrs=""):
        def dec(fn):
            def load(self, *args, **kwargs):
                typ = get_type(self, *args, **kwargs)
                attributes = ' '.join(
                    [str(kwargs[a]) for a in attrs.split() if a in kwargs])
                conditions = {
                    'type': '"{}"'.format(typ),
                    'name': '"{}"'.format(name),
                    'attributes': '"{}"'.format(attributes),
                }
                if self.use_cache:
                    try:
                        for c in persistence.load('graph_cache', **conditions):
                            return pickle.loads(persistence.get(
                                c[default_string('content_hash')]))
                    except:
                        traceback.print_exc()
                        print_msg("Couldn't load graph cache", True)
                start = time.time()
                graph = fn(self, *args, **kwargs)
                duration = time.time() - start
                try:
                    persistence.delete('graph_cache', **conditions)
                    persistence.insert('graph_cache', {
                        'type': typ,
                        'name': name,
                        'duration': duration,
                        'attributes': attributes,
                        'content_hash': persistence.put(pickle.dumps(graph)),
                    })
                except:
                    traceback.print_exc()
                    print_msg("Couldn't store graph cache", True)
                return graph
            return load
        return dec
    return cache


class TreeElement(object):

    def __init__(self, level=-1, use_id=True):
        self.duration = 0
        self.count = 1
        self.repr = ""
        self.level = level
        self.use_id = use_id
        self.trial_id = 0

    def mean(self):
        if isinstance(self.duration, tuple):
            return (self.a.duration / self.a.count,
                    self.b.duration / self.b.count)
        return self.duration / self.count

    def visit(self, visitor):
        name = "visit_{}".format(self.__class__.__name__.lower())
        return getattr(visitor, name)(self)

    def calculate_repr(self):
        pass

    def mix(self, other):
        pass

    def __hash__(self):
        if self.use_id:
            return id(self)
        return hash(self.__repr__())

    def __repr__(self):
        return self.repr

    def to_dict(self, nid):
        return {}


class Single(TreeElement):

    def __init__(self, activation):
        self.activation = activation
        self.activations = {activation}
        self.parent = activation['caller_id']
        self.id = activation['id']
        self.line = activation['line']
        self.name = activation['name']
        self.trial_id = activation['trial_id']
        self.repr = "S({0}-{1})".format(self.line, self.name)
        self.use_id = True
        self.level = 0

    @property
    def count(self):
        return sum(1 for a in self.activations)

    @count.setter
    def count(self, value):
        pass

    @property
    def duration(self):
        return sum(calculate_duration(a) for a in self.activations
                   if a['finish'] and a['start'])

    @duration.setter
    def duration(self, value):
        pass

    def mix(self, other):
        self.count += other.count
        self.duration += other.duration
        self.activations = self.activations.union(other.activations)

    def __eq__(self, other):
        return all(fn(self) == fn(other) for fn in
                   [type, lambda x: x.line, lambda x: x.name])

    def name_id(self):
        return "{0} {1}".format(self.line, self.name)

    def visit(self, visitor):
        return visitor.visit_single(self)

    def to_dict(self, nid):
        return {
            'index': nid,
            'caller_id': self.parent,
            'name': self.name,
            'node': {
                'trial_id': self.trial_id,
                'line': self.line,
                'count': self.count,
                'duration': self.duration,
                'level': self.level,
                'info': Info(self),
            }
        }

    def __hash__(self):
        return super(Single, self).__hash__()


class Mixed(TreeElement):

    def __init__(self, activation):
        self.duration = activation.duration
        self.elements = [activation]
        self.parent = activation.parent
        self.id = activation.id
        self.repr = activation.repr
        self.use_id = True
        self.level = 0

    @property
    def count(self):
        return sum(e.count for e in self.elements)

    @count.setter
    def count(self, value):
        pass

    @property
    def duration(self):
        return sum(e.duration for e in self.elements)

    @property
    def first(self):
        return next(iter(self.elements))

    @duration.setter
    def duration(self, value):
        pass

    def add_element(self, element):
        self.elements.append(element)

    def mix(self, other):
        self.elements += other.elements
        self.mix_results()

    def mix_results(self):
        it = iter(self.elements)
        initial = next(it)
        for element in it:
            initial.mix(element)

    def __hash__(self):
        return super(Mixed, self).__hash__()


class Group(TreeElement):

    def __init__(self):
        self.nodes = OrderedDict()
        self.edges = OrderedDict()
        self.duration = 0
        self.parent = None
        self.count = 1
        self.repr = ""
        self.use_id = True
        self.level = 0

    def initialize(self, previous, next):
        self.nodes[next] = Mixed(next)
        self.duration = next.duration
        self.next_element = next
        self.last = next
        self.add_subelement(previous)
        self.parent = next.parent
        return self

    def add_subelement(self, previous):
        next, self.next_element = self.next_element, previous
        if not previous in self.edges:
            self.edges[previous] = OrderedCounter()
        if not previous in self.nodes:
            self.nodes[previous] = Mixed(previous)
        else:
            self.nodes[previous].add_element(previous)
        self.edges[previous][next] += 1

    def calculate_repr(self):
        result = [
            "[{0}-{1}->{2}]".format(previous, count, next)
            for previous, edges in items(self.edges)
            for next, count in items(edges)
        ]

        self.repr = "G({0})".format(', '.join(result))

    def __eq__(self, other):
        return all(fn(self) == fn(other) for fn in
                   [type, lambda x: x.edges])

    def mix(self, other):
        for node, value in items(self.nodes):
            value.mix(other.nodes[node])

    def __hash__(self):
        return super(Group, self).__hash__()


class Call(TreeElement):

    def __init__(self, caller, called):
        self.caller = caller
        self.called = called
        self.called.calculate_repr()
        self.parent = caller.parent
        self.count = 1
        self.id = self.caller.id
        self.duration = self.caller.duration
        self.repr = 'C({0}, {1})'.format(self.caller, self.called)
        self.use_id = True
        self.level = 0

    def __eq__(self, other):
        return all(fn(self) == fn(other) for fn in
                   [type, lambda x: x.caller, lambda x: x.called])

    def mix(self, other):
        self.caller.mix(other.caller)
        self.called.mix(other.called)

    def __hash__(self):
        return super(Call, self).__hash__()


class Info(object):

    def __init__(self, single):
        self.title = ("Trial {trial}<br>"
                      "Function <b>{name}</b> called at line {line}").format(
            trial=single.trial_id, name=single.name, line=single.line)
        self.activations = set()
        self.duration = ""
        self.mean = ""
        self.extract_activations(single)

    def update_by_node(self, node):
        self.duration = self.duration_text(node['duration'], node['count'])
        self.mean = self.mean_text(node['mean'])
        self.activation_list = sorted(self.activations, key=lambda a: a[0])

    def add_activation(self, activation):
        self.activations.add(
            (datetime.strptime(activation['start'], FORMAT), activation))

    def extract_activations(self, single):
        for activation in single.activations:
            self.add_activation(activation)

    def duration_text(self, duration, count):
        return "Total duration: {} microseconds for {} activations".format(
            duration, count)

    def mean_text(self, mean):
        return "Mean: {} microseconds per activation".format(mean)

    def activation_text(self, activation):
        values = cvmap(row_to_dict, persistence.load('object_value',
            function_activation_id=activation['id'], order='id'))
        values = [value for value in values if value['type'] == 'ARGUMENT']
        result = [
            "",
            "Activation #{id} from {start} to {finish} ({dur} microseconds)"
                .format(dur=calculate_duration(activation), **activation),
        ]
        if values:
            result.append("Arguments: {}".format(
                ", ".join("{}={}".format(value["name"], value["value"])
                    for value in values)))
        return result + [
            "Returned {}".format(activation['return'])
        ]

    def __repr__(self):
        result = [self.title, self.duration, self.mean]
        for activation in self.activation_list:
            result += self.activation_text(activation[1])

        return '<br/>'.join(result)

