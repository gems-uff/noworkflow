from __future__ import (absolute_import, print_function,
                        division, unicode_literals)

from collections import OrderedDict
from future.utils import viewvalues, viewkeys
from functools import wraps


class DependencyAware(object):
    """Store dependencies of an element"""

    def __init__(self, activation, active=True):
        self.dependencies = []
        self.activation = activation
        self.active = active

    def add(self, dependency):
        if self.active:
            self.dependencies.append(dependency)


class Arg(DependencyAware):
    """Represent a Call parameter"""

    def __init__(self, activation, star, call_id, value=None):
        super(Arg, self).__init__(activation)
        self.value = value
        self.star = star
        self.call_id = call_id

    def __repr__(self):
        return "{}{}".format("*" if self.star else "", self.value)


class Keyword(DependencyAware):
    """Represent a Call keyword parameter"""

    def __init__(self, activation, arg, call_id):
        super(Keyword, self).__init__(activation)
        self.value = None
        self.arg = arg
        self.call_id = call_id

    def __repr__(self):
        return "{}{}{}".format(
            self.arg, "=" if self.arg != "**" else "", self.value
        )


class Call(DependencyAware):
    """Represent a Call"""

    def __init__(self, activation, func, name, call_id):
        super(Call, self).__init__(activation)
        self.func = func
        self.name = name
        self.call_id = call_id
        self.args = []
        self.keywords = []
        self.with_definition = False
        self.definition_activation = None

    def __repr__(self):
        args = []
        if self.args:
            args.append(', '.join(repr(arg) for arg in self.args))
        if self.keywords:
            args.append(', '.join(repr(key) for key in self.keywords))

        return "{}({})".format(
            self.name,
           ', '.join(args)
        )


class Decorator(Call):
    """Represent a decorator"""

    def __init__(self, name, activation):
        super(Decorator, self).__init__(activation, None, name, -1)

    def __repr__(self):
        return "@{}".format(self.name)


class Parameter(object):

    def __init__(self, name, value, is_vararg=False):
        self.name = name
        self.value = value
        self.is_vararg = is_vararg
        self.dependencies = []
        self.filled = False
        self.default = None

    def __repr__(self):
        return "{} (depends on [{}])".format(
            self.name, ",".join(repr(x) for x in self.dependencies)
        )

class Dependency(object):

    def __init__(self, name, value, type_):
        self.name = name
        self.value = value
        self.type = type_

    def __repr__(self):
        if self.type in ("direct", "call"):
            return repr(self.name)
        elif self.type == "conditional":
            return "{!r}c".format(self.name)
        else:
            print(self.type)


class ExecutionCollector(object):

    def __init__(self):
        self.args = []
        self.keywords = []
        self.activation_stack = []

        self.dependency_stack = [DependencyAware(None, active=False)]

    def dep_name(self, var, value, type_):
        self.dependency_stack[-1].add(Dependency(var, value, type_))
        return value

    def arg(self, activation, star, call_id):
        """Capture call arg before"""
        self.dependency_stack.append(Arg(activation, star, call_id))
        return self._arg

    def _arg(self, value):
        """Capture call arg after"""
        arg = self.dependency_stack.pop()
        arg.value = value
        call = self.activation_stack[-1]
        if call.call_id == arg.call_id:
            call.args.append(arg)
        return value

    def keyword(self, activation, arg, call_id):
        """Capture call keyword before"""
        self.dependency_stack.append(Keyword(activation, arg, call_id))
        return self._keyword

    def _keyword(self, value):
        """Capture call keyword after"""
        keyword = self.dependency_stack.pop()
        keyword.value = value
        call = self.activation_stack[-1]
        if call.call_id == keyword.call_id:
            call.keywords.append(keyword)
        return value

    def script_start(self, path):
        """Start script"""
        print("start")
        call = Call(None, None, path, -1)
        self.activation_stack.append(call)
        return call

    def script_end(self, activation):
        """End script"""
        print("end")

    def call(self, activation, call_id, func, type_):
        """Capture call before"""
        call = Call(activation, func, func.__name__, call_id)
        call.dependency_type = type_
        self.activation_stack.append(call)
        self.dependency_stack.append(call)
        return self._call

    def _call(self, *args, **kwargs):
        """Capture call surround"""
        call = self.dependency_stack.pop()
        print(call, [a.dependencies for a in call.args])
        result = call.func(*args, **kwargs)
        self.dependency_stack[-1].add(Dependency(
            call, result, call.dependency_type
        ))
        self.activation_stack.pop()
        return result


    def default(self):
        """Capture default value before"""
        self.dependency_stack.append(DependencyAware(None))
        return self._default

    def _default(self, value):
        """Capture default value after"""
        self.dependency_stack.pop()
        return value

    def decorator(self, name, activation):
        """Capture decorator before"""
        self.dependency_stack.append(Decorator(name, activation))
        return self._decorator

    def _decorator(self, dec):
        """Capture decorator surround"""
        decorator = self.dependency_stack.pop()
        decorator.func = dec
        def decorate_func(func):
            decorator.args.append(
                Arg(decorator.activation, False, -1, value=func)
            )
            # capture time
            self.activation_stack.append(decorator)
            result = dec(func)
            self.dependency_stack[-1].add(
                Dependency(decorator, result, "decorator"))
            self.activation_stack.pop()
            # capture time
            return result
        return decorate_func

    def function_def_decorator(self, activation):
        """Decorate function definition with itself and activation"""
        def dec(function_def):
            @wraps(function_def)
            def new_function_def(*args, **kwargs):
                return function_def(new_function_def, activation,
                                    *args, **kwargs)
            return new_function_def
        return dec

    def _match_arguments(self, call, args, defaults, vararg, kwarg,
                         kwonlyargs):
        """Match arguments with parameters"""
        # Create parameters
        parameters = OrderedDict()
        len_positional = len(args) - len(defaults)
        for i, arg in enumerate(args):
            param = parameters[arg[0]] = Parameter(*arg)
            if i > len_positional:
                param.default = defaults[i - len_positional]
        if vararg:
            parameters[vararg[0]] = Parameter(*vararg, is_vararg=True)
        if kwonlyargs:
            for arg in kwonlyargs:
                parameters[arg[0]] = Parameter(*arg)
        if kwarg:
            parameters[kwarg[0]] = Parameter(*kwarg)

        parameter_order = list(viewvalues(parameters))
        last_unfilled = 0

        # Match args
        for arg in call.args:
            if arg.star:
                for _ in range(len(arg.value)):
                    param = parameter_order[last_unfilled]
                    param.dependencies.append(arg)
                    if param.is_vararg:
                        break
                    param.filled = True
                    last_unfilled += 1
            else:
                param = parameter_order[last_unfilled]
                param.dependencies.append(arg)
                if not param.is_vararg:
                    param.filled = True
                    last_unfilled += 1

        if vararg:
            parameters[vararg[0]].filled = True

        # Match keywords
        for keyword in call.keywords:
            param = None
            if keyword.arg in parameters:
                param = parameters[keyword.arg]
            elif kwarg:
                param = parameters[kwarg[0]]
            if param is not None:
                param.dependencies.append(keyword)
                param.filled = True
            elif keyword.arg == "**":
                for key in viewkeys(keyword.value):
                    if key in parameters:
                        param = parameters[key]
                        param.dependencies.append(keyword)
                        param.filled = True

    def function_def(self, me_func, definition_activation, *parameters):
        """Capture function definitions"""
        call = self.activation_stack[-1]
        if id(call.func) != id(me_func):
            return call
        call.with_definition = True
        call.definition_activation = definition_activation
        parameters = self._match_arguments(call, *parameters)
        #print("def> {} defined in {}".format(call, definition_activation))
        #print("def>", parameters)
        return call
        #print("def>", args, vararg, kwarg, kwonlyargs)
        # Todo capture default

    def lambda_def(self, me_func, definition_activation, value, *parameters):
        call = self.activation_stack[-1]
        if id(call.func) != id(me_func):
            return call
        call.with_definition = True
        call.definition_activation = definition_activation
        parameters = self._match_arguments(call, *parameters)
        return value





