# Copyright (c) 2015 Universidade Federal Fluminense (UFF)
# Copyright (c) 2015 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.

from __future__ import (absolute_import, print_function,
                        division, unicode_literals)

import sys
import time
from datetime import datetime
from collections import defaultdict, OrderedDict, Counter
from pyposast.cross_version import buffered_str


from ..formatter import PrettyLines
from ..persistence import row_to_dict, persistence
from ..utils import calculate_duration, FORMAT, print_msg
from ..utils.data import HashableDict
from ..graphs.trial_graph import TrialGraph
from ..cross_version import lmap, cvmap
from .model import Model
from .trial_prolog import TrialProlog
from .activation import Activation
from .function_def import FunctionDef


class Trial(Model):
    """ This model represents a trial
    Initialize it by passing the trial id:
        trial = Trial(2)

    There are four visualization modes for the graph:
        tree: activation tree without any filters
            trial.graph.mode = 0
        no match: tree transformed into a graph by the addition of sequence and
                  return edges and removal of intermediate call edges
            trial.graph.mode = 1
        exact match: calls are only combined when all the sub-call match
            trial.graph.mode = 2
        namesapce: calls are combined without considering the sub-calls
            trial.graph.mode = 3

    You can change the graph width and height by the variables:
        trial.graph.width = 600
        trial.graph.height = 400
    """

    DEFAULT = {
        'graph.width': 500,
        'graph.height': 500,
        'graph.mode': 3,
        'use_cache': True,
    }

    REPLACE = {
        'graph_width': 'graph.width',
        'graph_height': 'graph.height',
        'graph_mode': 'graph.mode',
    }

    def __init__(self, trial_ref=None, exit=False, script=None, **kwargs):
        super(Trial, self).__init__(trial_id=trial_ref, exit=exit, script=script,
                                    **kwargs)

        if not trial_ref:
            trial_ref = persistence.last_trial_id(script=script)
            self.use_cache = False

        trial_id = persistence.load_trial_id(trial_ref)

        if exit and trial_id is None:
            print_msg('inexistent trial id', True)
            sys.exit(1)

        self.id = trial_id
        self._info = None

        self.graph = TrialGraph(trial_id)

        self.initialize_default(kwargs)

        self.graph.use_cache = self.use_cache

        self.trial_prolog = TrialProlog(self)

    def query(self, query):
        return self.trial_prolog.query(query)

    def prolog_rules(self):
        return self.trial_prolog.export_rules()

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
    def script_content(self):
        """ Returns the "main" script content of the trial """
        return PrettyLines(
            buffered_str(persistence.get(self.code_hash)).split('/n'))

    @property
    def code_hash(self):
        """ Returns the hash code of the main script """
        info = self.info()
        return info['code_hash']

    @property
    def finished(self):
        return bool(self.info()['finish'])

    def _repr_html_(self):
        """ Displays d3 graph on ipython notebook """
        return self.graph._repr_html_(self)

    def info(self):
        """ Returns dict with the trial information, considering the duration """
        if self._info is None or not self.use_cache:
            self._info = row_to_dict(
                persistence.load_trial(self.id).fetchone())
            if self._info['finish']:
                self._info['duration'] = calculate_duration(self._info)
            else:
                self._info['duration'] = 0
        return self._info

    def function_defs(self):
        """ Returns a dict of function definitions """
        return {
            function['name']: function
            for function in cvmap(FunctionDef, persistence.load(
                'function_def', trial_id=self.id))
        }

    def head_trial(self, remove=False):
        """ Returns the parent trial object """
        parent_id = persistence.load_parent_id(self.script, remove=remove)
        return Trial(parent_id)

    def module(self, name, map_fn=row_to_dict):
        """Return the module with specified name"""
        _, result = self.modules(map_fn=map_fn)
        for module in result:
            if module['name'] == name:
                return module
        return None

    def modules(self, map_fn=row_to_dict):
        """ Returns the modules imported during the trial
            The first element is a list of local modules
            The second element is a list of external modules
        """
        dependencies = persistence.load_dependencies(self.id)
        result = lmap(map_fn, dependencies)
        local = [dep for dep in result
                 if dep['path'] and persistence.base_path in dep['path']]
        return local, result

    def environment(self):
        """ Returns a dict of environment variables """
        return {
            attr['name']: attr['value'] for attr in cvmap(row_to_dict,
                persistence.load('environment_attr', trial_id=self.id))
        }

    def file_accesses(self):
        """ Returns a list of file accesses """
        def get(activation_id):
            """ Get activation by id """
            try:
                return next(iter(self.activations(id=activation_id)))
            except StopIteration:
                return None
        file_accesses = persistence.load('file_access',
                                         trial_id=self.id)

        result = []
        for fa in cvmap(row_to_dict, file_accesses):
            stack = []
            function_activation = get(fa['function_activation_id'])
            while function_activation:
                function_name = function_activation['name']
                function_activation = get(function_activation['caller_id'])
                if function_activation:
                    stack.insert(0, function_name)
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
        _vars = cvmap(row_to_dict, persistence.load(
            'slicing_variable', trial_id=self.id, order='id ASC'))
        _variables = OrderedDict()
        for var in _vars:
            _variables[var['id']] = var
        _activations = lmap(Activation, persistence.load(
            'function_activation', trial_id=self.id, order='start',
            **conditions))
        for act in _activations:
            act['slicing_variables'] = tuple(cvmap(HashableDict,
                persistence.load('slicing_variable', activation_id=act['id'],
                    trial_id=self.id)))

            act['slicing_usages'] = tuple(cvmap(HashableDict, persistence.load(
                'slicing_usage', activation_id=act['id'], trial_id=self.id)))

            for usage in act['slicing_usages']:
                usage['variable'] = _variables[usage['variable_id']]

            act['slicing_dependencies'] = tuple(cvmap(HashableDict,
                persistence.load('slicing_dependency',
                    dependent_activation_id=act['id'],
                    trial_id=self.id)))

            for dep in act['slicing_dependencies']:
                dep['dependent_id'] = dep['dependent']
                dep['dependent'] = _variables[dep['dependent']]
                dep['supplier_id'] = dep['supplier']
                dep['supplier'] = _variables[dep['supplier']]
        return _activations

    def slicing_variables(self):
        """ Returns a list of slicing variables """
        return lmap(row_to_dict, persistence.load(
            'slicing_variable', trial_id=self.id, order='id ASC'))

    def slicing_usages(self):
        """ Returns a list of slicing usages """
        return lmap(row_to_dict, persistence.load(
            'slicing_usage', trial_id=self.id))

    def slicing_dependencies(self):
        """ Returns a list of slicing dependencies """
        return lmap(row_to_dict, persistence.load(
            'slicing_dependency', trial_id=self.id))

    def __repr__(self):
        return "Trial {}".format(self.id)