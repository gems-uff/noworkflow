# Copyright (c) 2016 Universidade Federal Fluminense (UFF)
# Copyright (c) 2016 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""Intermediate Tree Structures and Graph Structures"""
from __future__ import (absolute_import, print_function,
                        division, unicode_literals)


import json
import time
import traceback

from collections import OrderedDict

from future.utils import viewitems
from sqlalchemy import exc

from ....persistence import relational, content
from ....utils.cross_version import pickle
from ....utils.data import OrderedCounter
from ....utils.io import print_msg

from .. import GraphCache


class Graph(object):                                                             # pylint: disable=too-few-public-methods
    """Graph superclass. Handle json transformation"""
    def escape_json(self, data):                                                 # pylint: disable=no-self-use
        """Escape JSON"""
        data = json.dumps(data)
        return (data.replace("&", "\\u0026")
                .replace("<", "\\u003c")
                .replace(">", "\\u003e"))


def prepare_cache(get_type):
    """Decorator: Load graph from cache"""
    def cache(name, attrs=""):
        """Decorator: Load graph from cache"""
        def dec(func):
            """Decorator: Load graph from cache"""
            def load(self, *args, **kwargs):
                """Load graph from cache

                Find graph by type, name and attributes
                If graph is cached, return it

                Return:
                finished -- trial has finished
                graph -- cached trial graph
                """
                cache_session = relational.make_session()

                typ = get_type(self, *args, **kwargs)
                attributes = " ".join(str(kwargs[a])
                                      for a in attrs.split() if a in kwargs)

                information = (typ, name, attributes)
                if self.use_cache:
                    try:
                        caches = GraphCache.select_cache(*information,
                                                         session=cache_session)
                        for cache in caches:
                            result = pickle.loads(
                                content.get(cache.content_hash))
                            if not result[0]:
                                continue
                            cache_session.close()                                # pylint: disable=no-member
                            return result
                    except (ValueError, exc.SQLAlchemyError):
                        traceback.print_exc()
                        print_msg("Couldn't load graph cache", True)
                start = time.time()
                graph = func(self, *args, **kwargs)
                duration = time.time() - start
                try:
                    GraphCache.remove(*information, session=cache_session)
                    GraphCache.create(
                        typ, name, duration, attributes,
                        content.put(pickle.dumps(graph)),
                        session=cache_session, commit=True
                    )
                except exc.SQLAlchemyError:
                    traceback.print_exc()
                    print_msg("Couldn't store graph cache", True)
                cache_session.close()                                            # pylint: disable=no-member
                return graph
            return load
        return dec
    return cache


class TreeElement(object):
    """Base class for Intermediate Tree"""

    def __init__(self, level=-1, use_id=True):
        self.duration = 0
        self.count = 1
        self.repr = ""
        self.level = level
        self.use_id = use_id
        self.trial_id = 0

    def mean(self):
        """Mean duration of Tree Node"""
        return self.duration / self.count

    def visit(self, visitor):
        """Visitor pattern"""
        name = "visit_{}".format(self.__class__.__name__.lower())
        return getattr(visitor, name)(self)

    def calculate_repr(self):
        """Calculate Representation of Node"""
        pass

    def mix(self, other):
        """Combine Nodes"""
        pass

    def __hash__(self):
        if self.use_id:
            return id(self)
        return hash(self.__repr__())

    def __repr__(self):
        return self.repr

    def to_dict(self, nid):                                                      # pylint: disable=unused-argument, no-self-use
        """Convert element to dict"""
        return {}


class Single(TreeElement):                                                       # pylint: disable=too-many-instance-attributes
    """Single Node
       Represent an activation or a group of merged activations"""
    def __init__(self, activation):
        super(Single, self).__init__(level=0, use_id=True)
        self.activation = activation
        self.activations = {activation}
        self.parent = activation.caller_id
        self.id = activation.id                                                  # pylint: disable=invalid-name
        self.line = activation.line

        name = activation.name
        if activation.name == "_handle_fromlist":
            for argument in activation.arguments:
                if argument.name == "module":
                    name = (
                        argument.value
                        .split("' from '")[-1]
                        .split('" from "')[-1]
                        [:-2]
                    )
        self.name = name
        self.trial_id = activation.trial_id
        self.repr = "S({0}-{1})".format(self.line, self.name)
        self.finished = bool(activation.finish)

    @property
    def count(self):
        """Count activations"""
        return sum(1 for a in self.activations)

    @count.setter
    def count(self, value):
        """Ignore set count"""
        pass

    @property
    def duration(self):
        """Calculate total duration"""
        return sum(a.duration for a in self.activations
                   if a.finish and a.start)

    @duration.setter
    def duration(self, value):
        """Ignore set duration"""
        pass

    def mix(self, other):
        """Combine activations"""
        self.finished &= other.finished
        self.count += other.count
        self.duration += other.duration
        self.activations = self.activations.union(other.activations)

    def __eq__(self, other):
        return all(fn(self) == fn(other) for fn in
                   [type, lambda x: x.line, lambda x: x.name])

    def name_id(self):
        """Return name that identifies node"""
        return "{0} {1}".format(self.line, self.name)

    def visit(self, visitor):
        return visitor.visit_single(self)

    def to_dict(self, nid):
        return {
            "index": nid,
            "caller_id": self.parent,
            "name": self.name,
            "node": {
                "trial_id": self.trial_id,
                "line": self.line,
                "count": self.count,
                "duration": self.duration,
                "level": self.level,
                "finished": self.finished,
                "info": Info(self),
            },
        }

    def __hash__(self):
        return super(Single, self).__hash__()


class Mixed(TreeElement):
    """Mixed Node
       Represent complex Mixed Node"""
    def __init__(self, activation):
        super(Mixed, self).__init__(level=0, use_id=True)
        self.duration = activation.duration
        self.elements = [activation]
        self.parent = activation.parent
        self.id = activation.id                                                  # pylint: disable=invalid-name
        self.repr = activation.repr
        self.finished = activation.finished

    @property
    def count(self):
        """Count activations"""
        return sum(e.count for e in self.elements)

    @count.setter
    def count(self, value):
        """Ignore set count"""
        pass

    @property
    def duration(self):
        """Calculate total duration"""
        return sum(e.duration for e in self.elements)

    @duration.setter
    def duration(self, value):
        """Ignore set duration"""
        pass

    @property
    def first(self):
        """Get first node"""
        return next(iter(self.elements))

    def add_element(self, element):
        """Add node"""
        self.finished &= element.finished
        self.elements.append(element)

    def mix(self, other):
        """Add nodes"""
        for element in other.elements:
            self.finished &= element.finished

        self.elements += other.elements
        self.mix_results()

    def mix_results(self):
        """Combine results"""
        iterator = iter(self.elements)
        initial = next(iterator)
        for element in iterator:
            initial.mix(element)

    def __hash__(self):
        return super(Mixed, self).__hash__()


class Group(TreeElement):                                                        # pylint: disable=too-many-instance-attributes
    """Group Node
       Represent a group of called nodes"""
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
        """Initialize the group node by two nodes"""
        self.nodes[nnext] = Mixed(nnext)
        self.duration = nnext.duration
        self.next_element = nnext
        self.last = nnext
        self.add_subelement(previous)
        self.parent = nnext.parent
        self.finished = previous.finished and nnext.finished
        return self

    def add_subelement(self, previous):
        """Add new node in sequence to group"""
        self.finished &= previous.finished
        nnext, self.next_element = self.next_element, previous
        if previous not in self.edges:
            self.edges[previous] = OrderedCounter()
        if previous not in self.nodes:
            self.nodes[previous] = Mixed(previous)
        else:
            self.nodes[previous].add_element(previous)
        self.edges[previous][nnext] += 1

    def calculate_repr(self):
        result = [
            "[{0}-{1}->{2}]".format(previous, count, nnext)
            for previous, edges in viewitems(self.edges)
            for nnext, count in viewitems(edges)
        ]

        self.repr = "G({0})".format(", ".join(result))

    def __eq__(self, other):
        return all(fn(self) == fn(other) for fn in
                   [type, lambda x: x.edges])

    def mix(self, other):
        for node, value in viewitems(self.nodes):
            value.mix(other.nodes[node])

    def __hash__(self):
        return super(Group, self).__hash__()


class Call(TreeElement):                                                         # pylint: disable=too-many-instance-attributes
    """Call Node
       Represent a call from a Node to a Group"""
    def __init__(self, caller, called):
        super(Call, self).__init__(level=0, use_id=True)
        self.caller = caller
        self.called = called
        self.called.calculate_repr()
        self.parent = caller.parent
        self.count = 1
        self.id = self.caller.id                                                 # pylint: disable=invalid-name
        self.duration = self.caller.duration
        self.repr = "C({0}, {1})".format(self.caller, self.called)
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
    """Return duration text"""
    return "Total duration: {} microseconds for {} activations".format(
        duration, count)


def mean_text(mean):
    """Return mean text"""
    return "Mean: {} microseconds per activation".format(mean)


def activation_text(activation):
    """Return single activation text"""
    extra = "(still running)"
    if activation.finish:
        extra = "to {a.finish} ({d} microseconds)".format(
            d=activation.duration, a=activation)
    result = [
        "",
        "Activation #{a.id} from {a.start} {extra}".format(
            extra=extra, a=activation),
    ]

    activation.show(
        _print=lambda x, offset=0: result.append(offset * "&nbsp;" + x))

    return result


class Info(object):
    """Info class
       Represent the information of a node"""

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
        """Update information by node"""
        self.duration = duration_text(node["duration"], node["count"])
        self.mean = mean_text(node["mean"])
        self.activation_list = sorted(self.activations, key=lambda a: a[0])

    def add_activation(self, activation):
        """Add activation information"""
        self.activations.add((activation.start, activation))

    def extract_activations(self, single):
        """Add activations information"""
        for activation in single.activations:
            self.add_activation(activation)

    def __repr__(self):
        result = [self.title, self.duration, self.mean]
        if self.activation_list is not None:
            for activation in self.activation_list:
                result += activation_text(activation[1])

        return "<br/>".join(result)
