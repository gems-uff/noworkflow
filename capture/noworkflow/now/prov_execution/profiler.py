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
import traceback
import time
from profile import Profile
from datetime import datetime
from .base import StoreOpenMixin
from .data_objects import Activation, ObjectStore, FileAccess, ObjectValue
from ..persistence import persistence


class Profiler(StoreOpenMixin):

    def __init__(self, *args):
        super(Profiler, self).__init__(*args)
        # the number of user functions activated
        #   (starts with -1 to compensate the first call to the script itself)
        self.depth_user = -1
        # the number of non-user functions activated
        self.depth_non_user = 0
        # The first caller is None
        self.activation_stack = [None]

        # Store provenance
        self.activations = ObjectStore(Activation)
        self.object_values = ObjectStore(ObjectValue)

        # Avoid using the same event for tracer and profiler
        self.last_event = None

        self.definition = self.metascript.definition
        self.functions = self.definition.functions

        self.event_map['c_call'] = self.trace_c_call
        self.event_map['call'] = self.trace_call
        self.event_map['c_return'] = self.trace_c_return
        self.event_map['c_exception'] = self.trace_c_exception
        self.event_map['return'] = self.trace_return

        # Partial save
        self.save_frequency = self.metascript.save_frequency / 1000.0
        self.call_storage_frequency = self.metascript.call_storage_frequency
        self.closed_activations = 0
        
        self.timer = time.time
        self.last_time = self.timer()

        # Events are unique
        self.unique_events = True

        # Skip tear_up return
        self.skip_first_return = True
        self.enabled = True

    @property
    def current_activation(self):
        return self._current_activation()

    @property
    def parent_activation(self):
        return self.activations[self.activation_stack[-2]]

    def _current_activation(self, ignore_open=False):
        astack = self.activation_stack
        if astack[-1]:
            activation = self.activations[astack[-1]]
            if ignore_open and len(astack) > 1 and activation.name == 'open':
                # get open's parent activation
                return self.activations[astack[-2]]
            return activation
        return Activation(-1, 'empty', 0, 0, -1)

    def add_file_access(self, file_access):
        # Wait activation that called open to finish
        activation = self._current_activation(ignore_open=True)
        file_access.function_activation_id = activation.id
        activation.file_accesses.append(file_access)

    def valid_depth(self):
        depth = self.depth_user + self.depth_non_user
        if depth < 0:
            self.enabled = False
            return False
        if depth > self.depth_threshold:
            return False
        return self.depth_non_user <= self.non_user_depth_threshold

    def add_activation(self, aid):
        self.activation_stack.append(aid)

    def close_activation(self, event, arg):
        activation = self.current_activation
        self.activation_stack.pop()
        activation.finish = datetime.now()
        try:
            if event == 'return':
                activation.return_value = self.serialize(arg)
        except:  # ignoring any exception during capture
            activation.return_value = None
        # Update content of accessed files
        for file_access in activation.file_accesses:
            # Checks if file still exists
            if os.path.exists(file_access.name):
                with persistence.std_open(file_access.name, 'rb') as f:
                    file_access.content_hash_after = persistence.put(f.read())
            file_access.done = True
        self.closed_activations += 1
        if self.call_storage_frequency and self.closed_activations % self.call_storage_frequency == 0:
            self.store(partial=True)

    def trace_c_call(self, frame, event, arg):
        self.depth_non_user += 1
        if self.valid_depth():
            self.add_activation(self.activations.add(
                arg.__name__ if arg.__self__ == None else '.'.join(
                    [type(arg.__self__).__name__, arg.__name__]),
                frame.f_lineno, frame.f_lasti, self.activation_stack[-1]
            ))

    def capture_python_params(self, frame, activation):
        values = frame.f_locals
        co = frame.f_code
        names = co.co_varnames
        nargs = co.co_argcount
        # Capture args
        for var in itertools.islice(names, 0, nargs):
            try:
                self.object_values.add(
                    var, self.serialize(values[var]), 'ARGUMENT', activation.id)
                activation.args.append(var)
            except Exception:
                # ignoring any exception during capture
                pass
        # Capture *args
        if co.co_flags & inspect.CO_VARARGS:
            varargs = names[nargs]
            self.object_values.add(
                varargs, self.serialize(values[varargs]), 'ARGUMENT', activation.id)
            activation.starargs.append(varargs)
            nargs += 1
        # Capture **kwargs
        if co.co_flags & inspect.CO_VARKEYWORDS:
            kwargs = values[names[nargs]]
            for key in kwargs:
                self.object_values.add(
                    key, self.serialize(kwargs[key]), 'ARGUMENT', activation.id)
            activation.kwargs.append(names[nargs])

    def trace_call(self, frame, event, arg):
        co_name = frame.f_code.co_name
        co_filename = frame.f_code.co_filename
        if co_filename in self.paths:
            self.depth_user += 1
        else:
            self.depth_non_user += 1

        if self.valid_depth():
            aid = self.activations.add(
                co_name if co_name != '<module>' else co_filename,
                frame.f_back.f_lineno, frame.f_back.f_lasti,
                self.activation_stack[-1]
            )
            activation = self.activations[aid]
            # Capturing arguments
            self.capture_python_params(frame, activation)

            # Capturing globals
            functions = self.functions.get(co_filename)
            if functions:
                function_def = functions.get(activation.name)

                if function_def:
                    fglobals = frame.f_globals
                    for global_var in function_def[1]:
                        self.object_values.add(
                            global_var, self.serialize(fglobals[global_var]),
                            'GLOBAL', aid)

            activation.start = datetime.now()
            self.add_activation(aid)

    def trace_c_return(self, frame, event, arg):
        if self.valid_depth():
            self.close_activation(event, arg)
        self.depth_non_user -= 1

    def trace_c_exception(self, frame, event, arg):
        if self.valid_depth():
            self.close_activation(event, arg)
        self.depth_non_user -= 1

    def trace_return(self, frame, event, arg):
        # Only enable activations gathering after the first call to the script
        if self.skip_first_return:
            self.skip_first_return = False
            return

        if self.valid_depth():
            self.close_activation(event, arg)

        if frame.f_code.co_filename in self.paths:
            self.depth_user -= 1
        else:
            self.depth_non_user -= 1

    def new_event(self, frame, event, arg):
        current_event = (event, frame.f_lineno, id(frame))
        if self.last_event != current_event:
            self.last_event = current_event
            return True
        return False

    def tracer(self, frame, event, arg):
        try:
            if self.enabled:
                if self.unique_events or self.new_event(frame, event, arg):
                    super(Profiler, self).tracer(frame, event, arg)
                if self.save_frequency and self.timer() - self.last_time > self.save_frequency:
                    self.store(partial=True)
                    self.last_time = self.timer()
        except:
            traceback.print_exc()
        finally:
            return self.tracer

    def store(self, partial=False):
        tid = self.trial_id
        if not partial:
            now = datetime.now()
            persistence.update_trial(tid, now, partial)
        persistence.store_activations(tid, self.activations, partial)
        persistence.store_object_values(tid, self.object_values, partial)
        persistence.store_file_accesses(tid, self.file_accesses, partial)

    def tearup(self):
        sys.setprofile(self.tracer)

    def teardown(self):
        super(Profiler, self).teardown()
        sys.setprofile(self.default_profile)


class InspectProfiler(Profiler):
    """ This Profiler uses the inspect.getargvalues that is slower because
    it considers the existence of anonymous tuple """

    def capture_python_params(self, frame, activation):
        (args, varargs, keywords, values) = inspect.getargvalues(frame)
        for arg in args:
            try:
                self.object_values.add(
                    arg, self.serialize(values[arg]), 'ARGUMENT', activation.id)
                activation.args.append(arg)
            except:  # ignoring any exception during capture
                pass
        if varargs:
            self.object_values.add(
                varargs, self.serialize(values[varargs]), 'ARGUMENT', activation.id)
            activation.starargs.append(varargs)
        if keywords:
            for key, value in items(values[keywords]):
                self.object_values.add(
                    key, self.serialize(value), 'ARGUMENT', activation.id)
                activation.kwargs.append(key)
