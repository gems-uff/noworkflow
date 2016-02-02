# Copyright (c) 2016 Universidade Federal Fluminense (UFF)
# Copyright (c) 2016 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""Capture arguments from calls"""

from __future__ import (absolute_import, print_function,
                        division, unicode_literals)

import weakref
import itertools
import inspect

from future.utils import viewitems

from ...utils.functions import abstract

from ..prov_definition.utils import ClassDef, Assert, With, Decorator


WITHOUT_PARAMS = (ClassDef, Assert, With)


class ArgumentCaptor(object):                                                    # pylint: disable=too-few-public-methods
    """Collect arguments during calls"""

    def __init__(self, provider):
        self.provider = weakref.proxy(provider)

    def capture(self, frame, activation):                                        # pylint: disable=unused-argument, no-self-use
        """Abstract method for capture"""
        abstract()


class ProfilerArgumentCaptor(ArgumentCaptor):                                    # pylint: disable=too-few-public-methods
    """Collect arguments for profiler"""

    def __init__(self, *args, **kwargs):
        super(ProfilerArgumentCaptor, self).__init__(*args, **kwargs)
        self.f_locals = {}

    def capture(self, frame, activation):
        """Store argument object values


        Arguments:
        frame -- current frame, after trace call
        activation -- current activation
        """
        provider = self.provider
        self.f_locals = values = frame.f_locals
        code = frame.f_code
        names = code.co_varnames
        nargs = code.co_argcount
        # Capture args
        for var in itertools.islice(names, 0, nargs):
            try:
                provider.object_values.add(
                    var,
                    provider.serialize(values[var]), "ARGUMENT", activation.id)
                activation.args.append(var)
            except Exception:                                                    # pylint: disable=broad-except
                # ignoring any exception during capture
                pass
        # Capture *args
        if code.co_flags & inspect.CO_VARARGS:                                   # pylint: disable=no-member
            varargs = names[nargs]
            provider.object_values.add(
                varargs,
                provider.serialize(values[varargs]), "ARGUMENT", activation.id)
            activation.starargs.append(varargs)
            nargs += 1
        # Capture **kwargs
        if code.co_flags & inspect.CO_VARKEYWORDS:                               # pylint: disable=no-member
            kwargs = values[names[nargs]]
            for key in kwargs:
                provider.object_values.add(
                    key, provider.serialize(kwargs[key]), "ARGUMENT",
                    activation.id)
            activation.kwargs.append(names[nargs])


class InspectProfilerArgumentCaptor(ArgumentCaptor):                             # pylint: disable=too-few-public-methods
    """This Argument Captor uses the inspect.getargvalues that is slower
    because it considers the existence of anonymous tuple
    """

    def capture(self, frame, activation):
        """Store argument object values


        Arguments:
        frame -- current frame, after trace call
        activation -- current activation
        """
        provider = self.provider
        # ToDo #75: inspect.getargvalues was deprecated on Python 3.5
        # ToDo #75: use inspect.signature instead
        (args, varargs, keywords, values) = inspect.getargvalues(frame)
        for arg in args:
            try:
                provider.object_values.add(
                    arg, provider.serialize(values[arg]), "ARGUMENT",
                    activation.id)
                activation.args.append(arg)
            except Exception:  # ignoring any exception during capture           # pylint: disable=broad-except
                pass
        if varargs:
            provider.object_values.add(
                varargs, provider.serialize(values[varargs]), "ARGUMENT",
                activation.id)
            activation.starargs.append(varargs)
        if keywords:
            for key, value in viewitems(values[keywords]):
                provider.object_values.add(
                    key, provider.serialize(value), "ARGUMENT", activation.id)
                activation.kwargs.append(key)


class SlicingArgumentCaptor(ProfilerArgumentCaptor):
    """Create Slicing Variables for Arguments and dependencies between
    Parameters and Arguments"""


    def __init__(self, *args, **kwargs):
        super(SlicingArgumentCaptor, self).__init__(*args, **kwargs)
        self.caller, self.activation = None, None
        self.filename, self.line = "", 0

    def match_arg(self, passed, arg):
        """Match passed param with argument


        Arguments:
        passed -- Call Variable name
        arg -- Argument name
        """
        provider = self.provider
        activation = self.activation
        context = activation.context

        if arg in context:
            act_var = context[arg]
        else:
            vid = provider.add_variable(activation.id, arg,
                                        self.line, self.f_locals)
            act_var = provider.variables[vid]
            context[arg] = act_var

        if passed:
            caller = self.caller
            lasti_set = set()
            provider.add_dependency(activation, act_var, caller, passed,
                                    self.filename, lasti_set)
            provider.remove_return_lasti(lasti_set)

    def match_args(self, params, arg):
        """Match passed param with argument


        Arguments:
        params -- Call Variable names
        arg -- Argument name
        """
        for param in params:
            self.match_arg(param, arg)

    def _defined_call(self, back, function_name):
        """Return a call extracted from AST if it has arguments
        or None, otherwise


        Arguments:
        back -- parent call frame
        function_name -- current call name
        """
        lineno, lasti = back.f_lineno, back.f_lasti
        filename = self.filename
        provider = self.provider

        if (filename not in provider.paths
                or lineno in provider.imports[filename]):
            return
        if (function_name == "__enter__" and
                lasti in provider.with_enter_by_lasti[filename][lineno]):
            return
        if (function_name == "__exit__" and
                lasti in provider.with_exit_by_lasti[filename][lineno]):
            return
        if lasti in provider.iters[filename][lineno]:
            provider.next_is_iter = True
            return

        call = provider.call_by_lasti[filename][lineno][lasti]
        if (isinstance(call, WITHOUT_PARAMS) or
                (isinstance(call, Decorator) and not call.is_fn)):
            return

        return call

    def capture(self, frame, activation):                                        # pylint: disable=too-many-locals
        """Match call parameters to function arguments


        Arguments:
        frame -- current frame, after trace call
        activation -- current activation
        """
        super(SlicingArgumentCaptor, self).capture(frame, activation)
        provider = self.provider
        back = frame.f_back
        self.filename = back.f_code.co_filename

        call = self._defined_call(back, frame.f_code.co_name)
        if not call:
            return

        self.line = frame.f_lineno
        self.caller, self.activation = provider.current_activation, activation

        match_args, match_arg = self.match_args, self.match_arg
        act_args_index = activation.args.index

        # Check if it has starargs and kwargs
        sub = -[bool(activation.starargs), bool(activation.kwargs)].count(True)
        order = activation.args + activation.starargs + activation.kwargs
        activation_arguments = len(order) + sub
        used = [0 for _ in order]
        j = 0

        # Match positional arguments
        for i, call_arg in enumerate(call.args):
            j = i if i < activation_arguments else sub
            act_arg = order[j]
            match_args(call_arg, act_arg)
            used[j] += 1

        # Match keyword arguments
        for act_arg, call_arg in viewitems(call.keywords):
            try:
                i = act_args_index(act_arg)
                match_args(call_arg, act_arg)
                used[i] += 1
            except ValueError:
                for kwargs in activation.kwargs:
                    match_args(call_arg, kwargs)

        # Match kwargs, starargs
        # ToDo #75: Python 3.5 supports multiple keyword arguments and starargs
        # ToDo #75: improve matching
        #   Ignore default params
        #   Do not match f(**kwargs) with def(*args)
        args = [(k, order[k]) for k in range(len(used)) if not used[k]]
        for star in call.kwargs + call.starargs:
            for i, act_arg in args:
                match_args(star, act_arg)
                used[i] += 1

        # Create variables for unmatched arguments
        args = [(k, order[k]) for k in range(len(used)) if not used[k]]
        for i, act_arg in args:
            match_arg(None, act_arg)

        # Create dependencies between all parameters
        # ToDo #35: improve dependencies to use references.
        #   Do not create dependencies between all parameters
        lasti_set = set()
        provider.add_inter_dependencies(back, call.all_args(), self.caller,
                                        lasti_set)
        provider.remove_return_lasti(lasti_set)
