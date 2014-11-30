# Copyright (c) 2014 Universidade Federal Fluminense (UFF)
# Copyright (c) 2014 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.

from __future__ import (absolute_import, print_function,
                        division, unicode_literals)


import sys
import os
import itertools
import inspect
from datetime import datetime
from .base import StoreOpenMixin
from .activation import Activation

from ..persistence import persistence

class Profiler(StoreOpenMixin):

    def __init__(self, *args):
        super(Profiler, self).__init__(*args)
        # the number of user functions activated
        #   (starts with -1 to compensate the first call to the script itself)
        self.depth_user = -1
        # the number of non-user functions activated
        self.depth_non_user = 0
        self.activation_stack = []
        self.function_activation = None

        self.event_map['c_call'] = self.trace_c_call
        self.event_map['call'] = self.trace_call
        self.event_map['c_return'] = self.trace_c_return
        self.event_map['c_exception'] = self.trace_c_exception
        self.event_map['return'] = self.trace_return

    def add_file_access(self, file_access):
        self.activation_stack[-1].file_accesses.append(file_access)

    def valid_depth(self):
        depth = self.depth_user + self.depth_non_user
        valid_all_threshold = depth <= self.depth_threshold
        valid_non_user_threshold = self.depth_non_user <= self.depth_threshold
        return ((self.depth_context == 'all' and valid_threshold) or
               (self.depth_context == 'non-user' and valid_non_user_threshold))

    def add_activation(self, activation):
        if activation:
            activation.start = datetime.now()
            self.activation_stack.append(activation)

    def close_activation(self, event, arg):
        activation = self.activation_stack.pop()
        activation.finish = datetime.now()
        try:
            activation.return_value = repr(arg) if event == 'return' else None
        except:  # ignoring any exception during capture
            activation.return_value = None
        # Update content of accessed files
        for file_access in activation.file_accesses:
            # Checks if file still exists
            if os.path.exists(file_access['name']):
                with persistence.std_open(file_access['name'], 'rb') as f:
                    file_access['content_hash_after'] = persistence.put(
                        f.read())

        if self.activation_stack:
            # Store the current activation in the previous activation
            self.activation_stack[-1].function_activations.append(activation)
        else:
            # Store the current activation as the first activation
            self.function_activation = activation
            self.enabled = False

    def trace_c_call(self, frame, event, arg):
        self.depth_non_user += 1
        if self.valid_depth():
            self.add_activation(Activation(
                arg.__name__ if arg.__self__ == None else '.'.join(
                    [type(arg.__self__).__name__, arg.__name__]),
                frame.f_lineno, frame.f_lasti
            ))

    def capture_python_params(self, frame, activation):
        values = frame.f_locals
        co = frame.f_code
        names = co.co_varnames
        nargs = co.co_argcount
        # Capture args
        for var in itertools.islice(names, 0, nargs):
            try:
                activation.arguments[var] = repr(values[var])
                activation.args.append(var)
            except:
                # ignoring any exception during capture
                pass
        # Capture *args
        if co.co_flags & inspect.CO_VARARGS:
            varargs = names[nargs]
            activation.arguments[varargs] = repr(values[varargs])
            activation.starargs.append(varargs)
            nargs += 1
        # Capture **kwargs
        if co.co_flags & inspect.CO_VARKEYWORDS:
            kwargs = values[names[nargs]]
            for key in kwargs:
                activation.arguments[key] = repr(kwargs[key])
            activation.kwargs.append(names[nargs])

    def trace_call(self, frame, event, arg):
        #print("now", frame.f_back.f_lineno, frame.f_code.co_name)
        co_name = frame.f_code.co_name
        co_filename = frame.f_code.co_filename
        if self.script == co_filename:
            self.depth_user += 1
        else:
            self.depth_non_user += 1

        if self.valid_depth():
            activation =  Activation(
                co_name if co_name != '<module>' else co_filename,
                frame.f_back.f_lineno, frame.f_back.f_lasti
            )
            # Capturing arguments
            self.capture_python_params(frame, activation)

            # Capturing globals
            function_def = persistence.load(
                'function_def',
                name = repr(activation.name),
                trial_id = self.trial_id
            ).fetchone()

            if function_def:
                global_vars = persistence.load(
                    'object',
                    type='"GLOBAL"',
                    function_def_id = function_def[str('id')]
                )
                aglobals = activation.globals
                fglobals = frame.f_globals
                for global_var in global_vars:
                    aglobals[global_var['name']] = fglobals[global_var['name']]

            self.add_activation(activation)

    def trace_c_return(self, frame, event, arg):
        if self.valid_depth():
            self.close_activation(event, arg)
        self.depth_non_user -= 1

    def trace_c_exception(self, frame, event, arg):
        if self.valid_depth():
            self.close_activation(event, arg)
        self.depth_non_user -= 1

    def trace_return(self, frame, event, arg):
        if self.valid_depth():
            self.close_activation(event, arg)

        if self.script == frame.f_code.co_filename:
            self.depth_user -= 1
        else:
            self.depth_non_user -= 1

    def tracer(self, frame, event, arg):
        # Only enable activations gathering after the first call to the script
        co_filename = frame.f_code.co_filename
        if not self.enabled and event == 'call' and self.script == co_filename:
            self.enabled = True

        if self.enabled:
            super(Profiler, self).tracer(frame, event, arg)
        return self.tracer

    def store(self):
        now = datetime.now()
        persistence.update_trial(self.trial_id, now, self.function_activation)

    def tearup(self):
        sys.setprofile(self.tracer)


class InspectProfiler(Profiler):
    """ This Profiler uses the inspect.getargvalues that is slower because
    it considers the existence of anonymous tuple """

    def capture_python_params(self, frame, activation):
        (args, varargs, keywords, values) = inspect.getargvalues(frame)
        for arg in args:
            try:
                activation.arguments[arg] = repr(values[arg])
                activation.args.append(arg)
            except:  # ignoring any exception during capture
                pass
        if varargs:
            activation.arguments[varargs] = repr(values[varargs])
            activation.starargs.append(varargs)
        if keywords:
            for key, value in values[keywords].iteritems():
                activation.arguments[key] = repr(value)
                activation.kwargs.append(key)
