# Copyright (c) 2015 Universidade Federal Fluminense (UFF)
# Copyright (c) 2015 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
""" Intermediate Tree Structures and Graph Structures """
from __future__ import (absolute_import, print_function,
                        division, unicode_literals)


import json
import time
import traceback
from collections import OrderedDict
from datetime import datetime
from sqlite3 import OperationalError

from ..cross_version import default_string, pickle, items
from ..persistence import persistence
from ..utils import calculate_duration, strptime, OrderedCounter, print_msg


class Graph(object):
    """ Graph superclass
        Handle json transformation"""
    # pylint: disable=R0201
    # pylint: disable=R0903
    def escape_json(self, data):
        """ Escape JSON """
        data = json.dumps(data)
        return (data.replace('&', '\\u0026')
                .replace('<', '\\u003c')
                .replace('>', '\\u003e'))


def prepare_cache(get_type):
    """ Decorator: Load graph from cache """
    def cache(name, attrs=""):
        """ Decorator: Load graph from cache """
        def dec(func):
            """ Decorator: Load graph from cache """
            def load(self, *args, **kwargs):
                """ Load graph from cache """
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
                        graph_cache = persistence.load('graph_cache',
                                                       **conditions)
                        for cache in graph_cache:
                            result = pickle.loads(persistence.get(
                                cache[default_string('content_hash')]))
                            if not result[0]:
                                continue
                            return result
                    except OperationalError:
                        traceback.print_exc()
                        print_msg("Couldn't load graph cache", True)
                start = time.time()
                graph = func(self, *args, **kwargs)
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
                except OperationalError:
                    traceback.print_exc()
                    print_msg("Couldn't store graph cache", True)
                return graph
            return load
        return dec
    return cache


class TreeElement(object):
    """ Base class for Intermediate Tree """

    def __init__(self, level=-1, use_id=True):
        self.duration = 0
        self.count = 1
        self.repr = ""
        self.level = level
        self.use_id = use_id
        self.trial_id = 0

    def mean(self):
        """ Mean duration of Tree Node """
        return self.duration / self.count

    def visit(self, visitor):
        """ Visitor pattern """
        name = "visit_{}".format(self.__class__.__name__.lower())
        return getattr(visitor, name)(self)

    def calculate_repr(self):
        """ Calculate Representation of Node """
        pass

    def mix(self, other):
        """ Combine Nodes """
        pass

    def __hash__(self):
        if self.use_id:
            return id(self)
        return hash(self.__repr__())

    def __repr__(self):
        return self.repr

    def to_dict(self, nid):
        """ Convert element to dict """
        return {}


class Single(TreeElement):
    """ Single Node
        Represent an activation or a group of merged activations """
    # pylint: disable=R0902
    # pylint: disable=C0103
    def __init__(self, activation):
        super(Single, self).__init__(level=0, use_id=True)
        self.activation = activation
        self.activations = {activation}
        self.parent = activation['caller_id']
        self.id = activation['id']
        self.line = activation['line']
        self.name = activation['name']
        self.trial_id = activation['trial_id']
        self.repr = "S({0}-{1})".format(self.line, self.name)
        self.finished = bool(activation['finish'])

    @property
    def count(self):
        """ Count activations """
        return sum(1 for a in self.activations)

    @count.setter
    def count(self, value):
        """ Ignore set count """
        pass

    @property
    def duration(self):
        """ Calculate total duration """
        return sum(calculate_duration(a) for a in self.activations
                   if a['finish'] and a['start'])

    @duration.setter
    def duration(self, value):
        """ Ignore set duration """
        pass

    def mix(self, other):
        """ Combine activations """
        self.finished &= other.finished
        self.count += other.count
        self.duration += other.duration
        self.activations = self.activations.union(other.activations)

    def __eq__(self, other):
        return all(fn(self) == fn(other) for fn in
                   [type, lambda x: x.line, lambda x: x.name])

    def name_id(self):
        """ Return name that identifies node """
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
                'finished': self.finished,
                'info': Info(self),
            },
        }

    def __hash__(self):
        return super(Single, self).__hash__()


class Mixed(TreeElement):
    """ Single Node
        Represent complex Mixed Node """
    # pylint: disable=R0902
    # pylint: disable=C0103
    def __init__(self, activation):
        super(Mixed, self).__init__(level=0, use_id=True)
        self.duration = activation.duration
        self.elements = [activation]
        self.parent = activation.parent
        self.id = activation.id
        self.repr = activation.repr
        self.finished = activation.finished

    @property
    def count(self):
        """ Count activations """
        return sum(e.count for e in self.elements)

    @count.setter
    def count(self, value):
        """ Ignore set count """
        pass

    @property
    def duration(self):
        """ Calculate total duration """
        return sum(e.duration for e in self.elements)

    @duration.setter
    def duration(self, value):
        """ Ignore set duration """
        pass

    @property
    def first(self):
        """ Get first node """
        return next(iter(self.elements))


    def add_element(self, element):
        """ Add node """
        self.finished &= element.finished
        self.elements.append(element)

    def mix(self, other):
        """ Add nodes """
        for element in other.elements:
            self.finished &= element.finished

        self.elements += other.elements
        self.mix_results()

    def mix_results(self):
        """ Combine results """
        it = iter(self.elements)
        initial = next(it)
        for element in it:
            initial.mix(element)

    def __hash__(self):
        return super(Mixed, self).__hash__()


class Group(TreeElement):
    """ Group Node
        Represent a group of called nodes """
    # pylint: disable=R0902
    def __init__(self):
        super(Group, self).__init__(level=0, use_id=True)
        self.nodes = OrderedDict()
        self.edges = OrderedDict()
        self.duration = 0
        self.parent = None
        self.count = 1
        self.repr = ""
        self.finished = True
        self.next_element = None
        self.last = None

    def initialize(self, previous, nnext):
        """ Initialize the group node by two nodes """
        self.nodes[nnext] = Mixed(nnext)
        self.duration = nnext.duration
        self.next_element = nnext
        self.last = nnext
        self.add_subelement(previous)
        self.parent = nnext.parent
        self.finished = previous.finished and nnext.finished
        return self

    def add_subelement(self, previous):
        """ Add new node in sequence to group """
        self.finished &= previous.finished
        nnext, self.next_element = self.next_element, previous
        if not previous in self.edges:
            self.edges[previous] = OrderedCounter()
        if not previous in self.nodes:
            self.nodes[previous] = Mixed(previous)
        else:
            self.nodes[previous].add_element(previous)
        self.edges[previous][nnext] += 1

    def calculate_repr(self):
        result = [
            "[{0}-{1}->{2}]".format(previous, count, nnext)
            for previous, edges in items(self.edges)
            for nnext, count in items(edges)
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
    """ Call Node
        Represent a call from a Node to a Group """
    # pylint: disable=R0902
    # pylint: disable=C0103
    def __init__(self, caller, called):
        super(Call, self).__init__(level=0, use_id=True)
        self.caller = caller
        self.called = called
        self.called.calculate_repr()
        self.parent = caller.parent
        self.count = 1
        self.id = self.caller.id
        self.duration = self.caller.duration
        self.repr = 'C({0}, {1})'.format(self.caller, self.called)
        self.finished = self.caller.finished

    def __eq__(self, other):
        return all(fn(self) == fn(other) for fn in
                   [type, lambda x: x.caller, lambda x: x.called])

    def mix(self, other):
        self.caller.mix(other.caller)
        self.called.mix(other.called)

    def __hash__(self):
        return super(Call, self).__hash__()


def duration_text(duration, count):
    """ Return duration text """
    return "Total duration: {} microseconds for {} activations".format(
        duration, count)


def mean_text(mean):
    """ Return mean text """
    return "Mean: {} microseconds per activation".format(mean)


def activation_text(activation):
    """ Return single activation text """
    values = activation.arguments
    extra = "(still running)"
    if activation['finish']:
        extra = "to {finish} ({d} microseconds)".format(
            d=calculate_duration(activation), **activation)
    result = [
        "",
        "Activation #{id} from {start} {extra}".format(
            extra=extra, **activation),
    ]
    if values:
        result.append("Arguments: {}".format(
            ", ".join("{}={}".format(value["name"], value["value"])
                      for value in values)))
    if activation['return']:
        result.append("Returned {}".format(activation['return']))
    if activation['slicing_variables']:
        result.append("Variables: <br>&nbsp; {}".format(
            "<br>&nbsp; ".join("(L{line}, {name}, {value})".format(**var)
                          for var in activation['slicing_variables'])))
    if activation['slicing_usages']:
        result.append("Usages: <br>&nbsp; {}".format(
            "<br>&nbsp; ".join("(L{line}, {name}, <{context}>)".format(**var)
                               for var in activation['slicing_usages'])))
    if activation['slicing_dependencies']:
        result.append("Dependencies: <br>&nbsp; {}".format(
            "<br>&nbsp; ".join(
                ('(L{dependent[line]}, {dependent[name]}, {dependent[value]}) '
                '<- (L{supplier[line]}, {supplier[name]}, {supplier[value]})'
                ).format(**dep)
                for dep in activation['slicing_dependencies'])))
    return result


class Info(object):
    """ Info class
        Represent the information of a node """

    def __init__(self, single):
        self.title = (
            "Trial {trial}<br>"
            "Function <b>{name}</b> called at line {line}").format(
                trial=single.trial_id, name=single.name, line=single.line)
        self.activations = set()
        self.duration = ""
        self.mean = ""
        self.extract_activations(single)
        self.activation_list = None

    def update_by_node(self, node):
        """ Update information by node """
        self.duration = duration_text(node['duration'], node['count'])
        self.mean = mean_text(node['mean'])
        self.activation_list = sorted(self.activations, key=lambda a: a[0])

    def add_activation(self, activation):
        """ Add activation information """
        self.activations.add((strptime(activation['start']), activation))

    def extract_activations(self, single):
        """ Add activations information """
        for activation in single.activations:
            self.add_activation(activation)

    def __repr__(self):
        result = [self.title, self.duration, self.mean]
        for activation in self.activation_list:
            result += activation_text(activation[1])

        return '<br/>'.join(result)

