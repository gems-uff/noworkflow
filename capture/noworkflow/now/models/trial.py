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
from ..graphs.trial_graph import TrialGraph
from .model import Model
from .trial_prolog import TrialProlog
from .activation import Activation


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
    }

    REPLACE = {
        'graph_width': 'graph.width',
        'graph_height': 'graph.height',
        'graph_mode': 'graph.mode',
    }

    def __init__(self, trial_id, exit=False, script=None, **kwargs):
        super(Trial, self).__init__(trial_id, exit=exit, script=script,
                                    **kwargs)
        self.graph = TrialGraph(trial_id)
        self.initialize_default(kwargs)

        if exit:
            last_trial_id = persistence.last_trial_id(script=script)
            trial_id = trial_id or last_trial_id
            if not 1 <= trial_id <= last_trial_id:
                print_msg('inexistent trial id', True)
                sys.exit(1)

        self.id = trial_id
        self._info = None
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

    def _repr_html_(self):
        """ Displays d3 graph on ipython notebook """
        return self.graph._repr_html_(self)

    def info(self):
        """ Returns dict with the trial information, considering the duration """
        if self._info is None:
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
            function['name']: row_to_dict(function)
            for function in persistence.load('function_def',
                                             trial_id=self.id)
        }

    def head_trial(self, remove=False):
        """ Returns the parent trial object """
        parent_id = persistence.load_parent_id(self.script, remove=remove)
        return Trial(parent_id)

    def modules(self, map_fn=row_to_dict, find=None):
        """ Returns the modules imported during the trial
            The first element is a list of local modules
            The second element is a list of external modules
        """
        dependencies = persistence.load_dependencies(self.id)
        result = list(map(map_fn, dependencies))
        local = [dep for dep in result
                 if dep['path'] and persistence.base_path in dep['path']]
        if find is None:
            return local, result
        for x in result:
            if x['name'] == find:
                return x
        return None

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
        return list(map(Activation, persistence.load('function_activation',
                                                trial_id=self.id,
                                                order='start',
                                                **conditions)))

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
