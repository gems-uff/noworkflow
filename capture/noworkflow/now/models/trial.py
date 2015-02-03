# Copyright (c) 2014 Universidade Federal Fluminense (UFF)
# Copyright (c) 2014 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.

from __future__ import (absolute_import, print_function,
                        division, unicode_literals)

import sys
from datetime import datetime
from collections import defaultdict, OrderedDict, Counter

from .. import utils
from ..persistence import row_to_dict, persistence
from .trial_activation_visitors import TrialGraphVisitor
from .trial_activation_visitors import TrialGraphCombineVisitor
from .trial_prolog import TrialProlog
from .utils import calculate_duration, FORMAT
from .activation import Activation

class Trial(object):
    """ This model represents a trial
    Initialize it by passing the trial id:
        trial = Trial(2)

    There are two visualization modes for the graph:
        exact match: calls are only combined when all the sub-call match
            trial.graph_type = 0
        combined: calls are combined without considering the sub-calls
            trial.graph_type = 1

    You can change the graph width and height by the variables:
        trial.graph_width = 600
        trial.graph_height = 400
    """

    def __init__(self, trial_id, script=None, exit=False):
        if exit:
            last_trial_id = persistence.last_trial_id(script=script)
            trial_id = trial_id or last_trial_id
            if not 1 <= trial_id <= last_trial_id:
                utils.print_msg('inexistent trial id', True)
                sys.exit(1)

        self.id = trial_id
        self._info = None
        self.prolog = None
        self._graph_types = {
            0: self.independent_activation_graph,
            1: self.combined_activation_graph
        }
        self.graph_width = 500
        self.graph_height = 500
        self.graph_type = 0

    def init_prolog(self):
        # Todo: fix prolog
        if not self.prolog:
            from pyswip import Prolog
            self.prolog = Prolog()
            self.trial_prolog = TrialProlog(self)
            for fact in self.trial_prolog.export_facts(with_doc=False):
                self.prolog.assertz(fact[:-1])
            for rule in self.trial_prolog.export_rules().split('\n'):
                rule = rule.strip()
                if not rule or rule[0] == '%':
                    continue
                self.prolog.assertz(rule[:-1])

    def query(self, prolog):
        self.init_prolog()
        return self.prolog.query(prolog)

    def prolog_rules(self):
        self.init_prolog()
        return self.trial_prolog.export_rules().split('\n')

    @property
    def trial_id(self):
        from warnings import warn
        warn('trial_id propery deprecated. Please use id')
        return self.id

    @property
    def script(self):
        """ Returns the "main" script of the trial """
        info = self.info()
        return info['script']

    @property
    def code_hash(self):
        """ Returns the hash code of the main script """
        info = self.info()
        return info['code_hash']

    def _ipython_display_(self):
        """ Displays d3 graph on ipython notebook """
        from IPython.display import (
            display_png, display_html, display_latex,
            display_javascript, display_svg
        )
        import json
        import time

        uid = str(int(time.time()*1000000))
        display_html("""
            <div class="now-trial now">
                <div>
                    <form class="toolbar">
                      <input id="showtooltips-{0}" type="checkbox" name="showtooltips" value="show">
                      <label for="showtooltips-{0}" title="Show tooltips on mouse hover"><i class="fa fa-comment"></i></label>
                    </form>
                    <div id='graph-{0}' class="now-trial-graph ipython-graph" style="width: {1}px; height: {2}px;"></div>
                </div>
            </div>""".format(uid, self.graph_width, self.graph_height), raw=True)
        display_javascript("""
            var trial_graph = now_trial_graph('#graph-{0}', {0}, {2}, {2}, {1}, {3}, {4}, "#showtooltips-{0}", {{
                custom_size: function() {{
                    return [{3}, {4}];
                }}
            }});
            $( "[name='showtooltips']" ).change(function() {{
                trial_graph.set_use_tooltip(d3.select("#showtooltips-{0}").property("checked"));
            }});
            """.format(
                uid,
                json.dumps(self._graph_types[self.graph_type]()),
                self.id, self.graph_width, self.graph_height), raw=True)

    def info(self):
        """ Returns dict with the trial information, considering the duration """
        if self._info is None:
            self._info = row_to_dict(
                persistence.load_trial(self.id).fetchone())
            if self._info['finish']:
                self._info['duration'] = calculate_duration(self._info)
        return self._info

    def function_defs(self):
        """ Returns a dict of function definitions """
        return {
            function['name']: row_to_dict(function)
            for function in persistence.load('function_def',
                                             trial_id=self.id)
        }

    def head_trial(self, remove=False):
        """ Returns the parent trial object """
        parent_id = persistence.load_parent_id(self.script, remove=remove)
        return Trial(parent_id)

    def modules(self, map_fn=row_to_dict):
        """ Returns the modules imported during the trial
            The first element is a list of local modules
            The second element is a list of external modules
        """
        dependencies = persistence.load_dependencies(self.id)
        result = map(map_fn, dependencies)
        local = [dep for dep in result
                 if dep['path'] and persistence.base_path in dep['path']]
        return local, result

    def environment(self):
        """ Returns a dict of environment variables """
        return {
            attr['name']: attr['value'] for attr in map(row_to_dict,
                persistence.load('environment_attr', trial_id=self.id))
        }

    def file_accesses(self):
        """ Returns a list of file accesses """
        file_accesses = persistence.load('file_access',
                                         trial_id=self.id)

        result = []
        for fa in map(row_to_dict, file_accesses):
            stack = []
            function_activation = next(iter(self.activations(
                id=fa['function_activation_id'])))
            while function_activation:
                function_name = function_activation['name']
                try:
                    function_activation = next(iter(self.activations(
                        id=function_activation['caller_id'])))
                    stack.insert(0, function_name)
                except StopIteration:
                    function_activation = None
            if not stack or stack[-1] != 'open':
                stack.append(' ... -> open')

            result.append({
                'id': fa['id'],
                'function_activation_id': fa['function_activation_id'],
                'name': fa['name'],
                'mode': fa['mode'],
                'buffering': fa['buffering'],
                'content_hash_before': fa['content_hash_before'],
                'content_hash_after': fa['content_hash_after'],
                'timestamp': fa['timestamp'],
                'stack': ' -> '.join(stack),
            })
        return result

    def activations(self, **conditions):
        """ Returns a list of activations """
        return map(Activation, persistence.load('function_activation',
                                                trial_id=self.id,
                                                order='start',
                                                **conditions))

    def slicing_variables(self):
        """ Returns a list of slicing variables """
        return persistence.load('slicing_variable',
                                trial_id=self.id,
                                order='vid ASC')

    def slicing_usages(self):
        """ Returns a list of slicing usages """
        return persistence.load('slicing_usage',
                                trial_id=self.id)

    def slicing_dependencies(self):
        """ Returns a list of slicing dependencies """
        return persistence.load('slicing_dependency',
                                trial_id=self.id)

    def activation_graph(self):
        """ Generates an activation graph """
        result_stack = []
        stack = [Single(act) for act in self.activations()]

        if not stack:
            return TreeElement()

        result_stack.append(stack.pop())
        while stack:
            next = result_stack.pop()
            previous = stack.pop()
            add_flow(stack, result_stack, previous, next)

        return result_stack.pop()

    def independent_activation_graph(self):
        """ Generates an activation graph and transforms it into an
            exact match graph supported by d3 """
        graph = self.activation_graph()
        visitor = TrialGraphVisitor()
        graph.visit(visitor)
        return visitor.to_dict()

    def combined_activation_graph(self):
        """ Generates an activation graph and transforms it into an
            combined graph supported by d3 """
        graph = self.activation_graph()
        visitor = TrialGraphCombineVisitor()
        graph.visit(visitor)
        return visitor.to_dict()


class TreeElement(object):

    def __init__(self):
        self.duration = 0
        self.count = 1
        self.repr = ""

    def mean(self):
        if isinstance(self.duration, tuple):
            return (self.a.duration / self.a.count,
                    self.b.duration / self.b.count)
        return self.duration / self.count

    def visit(self, visitor):
        return visitor.visit_default(self)

    def calculate_repr(self):
        pass

    def mix(self, other):
        pass

    def __hash__(self):
        #return id(self)
        return hash(self.__repr__())

    def __repr__(self):
        return self.repr


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
        if type(self) != type(other):
            return False
        if self.line != other.line:
            return False
        if self.name != other.name:
            return False
        return True

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
                'info': Info(self)
            }
        }


class Mixed(TreeElement):

    def __init__(self, activation):
        self.duration = activation.duration
        self.elements = [activation]
        self.parent = activation.parent
        self.id = activation.id
        self.repr = activation.repr

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

    def visit(self, visitor):
        return visitor.visit_mixed(self)

    def mix(self, other):
        self.elements += other.elements
        self.mix_results()

    def mix_results(self):
        it = iter(self.elements)
        initial = next(it)
        for element in it:
            initial.mix(element)


class Group(TreeElement):

    def __init__(self):
        self.nodes = OrderedDict()
        self.edges = OrderedDict()
        self.duration = 0
        self.parent = None
        self.count = 1
        self.repr = ""

    def initialize(self, previous, next):
        self.nodes[next] = Mixed(next)
        self.duration = next.duration
        self.next = next
        self.last = next
        self.add_subelement(previous)
        self.parent = next.parent
        return self

    def add_subelement(self, previous):
        next, self.next = self.next, previous
        if not previous in self.edges:
            self.edges[previous] = utils.OrderedCounter()
        if not previous in self.nodes:
            self.nodes[previous] = Mixed(previous)
        else:
            self.nodes[previous].add_element(previous)
        self.edges[previous][next] += 1

    def calculate_repr(self):
        result = [
            "[{0}-{1}->{2}]".format(previous, count, next)
            for previous, edges in self.edges.items()
            for next, count in edges.items()
        ]

        self.repr = "G({0})".format(', '.join(result))

    def __eq__(self, other):
        if type(self) != type(other):
            return False
        if not self.edges == other.edges:
            return False
        return True

    def visit(self, visitor):
        return visitor.visit_group(self)

    def mix(self, other):
        for node, value in self.nodes.items():
            value.mix(other.nodes[node])


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

    def __eq__(self, other):
        if type(self) != type(other):
            return False
        if not self.caller == other.caller:
            return False
        if not self.called == other.called:
            return False
        return True

    def visit(self, visitor):
        return visitor.visit_call(self)

    def mix(self, other):
        self.caller.mix(other.caller)
        self.called.mix(other.called)


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
        values = map(row_to_dict, persistence.load('object_value',
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


def join(a, b):
    if a == b:
        return Dual(a, b)
    return Branch(a, b)


def sequence(previous, next):
    if isinstance(next, Group):
        next.add_subelement(previous)
        return next
    return Group().initialize(previous, next)


def add_flow(stack, result, previous, next):
    if previous.parent == next.parent:
        # Same function level
        result.append(sequence(previous, next))

    elif previous.id == next.parent:
        # Previously called next
        # if top of result is in the same level of call:
        #   create sequece or combine results
        # if top of result is in a higher level, put Call on top of pile
        if result:
            add_flow(stack, result, Call(previous, next), result.pop())
        else:
            result.append(Call(previous, next))
    else:
        # Next is in a higher level
        # Put previous on top of result
        result.append(next)
        result.append(previous)
