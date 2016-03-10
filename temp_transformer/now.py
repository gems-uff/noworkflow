from __future__ import (absolute_import, print_function,
                        division, unicode_literals)

from collections import OrderedDict
from future.utils import viewvalues, viewkeys
from functools import wraps
from itertools import tee

from noworkflow.now.utils.cross_version import IMMUTABLE


class DependencyAware(object):
    """Store dependencies of an element"""

    def __init__(self, activation, active=True):
        self.dependencies = []
        self.activation = activation
        self.active = active

    def add(self, dependency):
        if self.active:
            self.dependencies.append(dependency)

class OrderedDependencyAware(DependencyAware):
    pass


class Variable(DependencyAware):

    def __init__(self, vid, activation, name, value=None, type_="normal"):
        super(Variable, self).__init__(activation)
        self.trial_id = None # ToDo
        self.activation_id = activation.id
        self.id = vid

        self.name = name
        self.line = None # ToDo
        self.time = None # ToDo
        self.type = type_

        self.immutable = False
        self.value_id = None
        self.value = value

        self.parts = {}

    @property
    def value(self):
        return self._value

    @value.setter
    def value(self, value):
        self.immutable = isinstance(value, IMMUTABLE)
        self._value = value
        self.value_id = id(value)

    def __repr__(self):
        return "{}".format(self.name)


class Activation(DependencyAware):
    """Represent a Call"""

    def __init__(self, aid, activation, func, name, call_id):
        super(Activation, self).__init__(activation)
        self.id = aid
        self.func = func
        self.name = name
        self.call_id = call_id
        self.args = []
        self.keywords = []
        self.with_definition = False
        self.definition_activation = None
        self.dependency_type = "direct"
        self.last_yield = None
        self.delay_conditions = []
        self.last_assignment = []
        self.variables = {}

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

    def __setitem__(self, variable_name, variable):
        self.variables[variable_name] = variable

    def __getitem__(self, variable_name):
        result = self.variables.get(variable_name, None)
        if not result:
            if not self.activation:
                return None
            result = self.activation[variable_name]
        return result



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

class ComprehensionResult(DependencyAware):
    """Represent a ComprehensionResult"""

    def __init__(self, activation, arg):
        super(ComprehensionResult, self).__init__(activation)
        self.value = None
        self.arg = arg

    def __repr__(self):
        return "{}".format(self.arg)

class ComprehensionCondition(DependencyAware):
    """Represent a ComprehensionCondition"""

    def __init__(self, activation):
        super(ComprehensionCondition, self).__init__(activation)
        self.value = None

    def __repr__(self):
        return "{}".format(self.value)



class Decorator(Activation):
    """Represent a decorator"""

    def __init__(self, did, name, activation):
        super(Decorator, self).__init__(did, activation, None, name, -1)

    def __repr__(self):
        return "@{}".format(self.name)

class Iterable(DependencyAware):

    def __init__(self, activation, unpack):
        super(Iterable, self).__init__(activation)
        self.unpack = unpack

    def __repr__(self):
        return "<iterable>"

class Assignment(DependencyAware):

    def __init__(self, activation):
        super(Assignment, self).__init__(activation)

    def __repr__(self):
        return "<Assignment>"

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

    def __init__(self, variable, value, type_):
        self.variable = variable
        self.value = value
        self.type = type_

    def __repr__(self):
        if self.type in ("direct", "call"):
            return repr(self.variable)
        elif self.type == "conditional":
            return "{!r}c".format(self.variable)
        else:
            print(self.type)

class Unpack(object):

    def __init__(self, var, _type):
        self.var = var
        self.type = _type

    def __repr__(self):
        return "Unpack({!r}, {})".format(self.var, self.type)

class ExecutionCollector(object):

    def __init__(self):
        self.args = []
        self.keywords = []
        self.activation_stack = []

        self.dependency_stack = [DependencyAware(None, active=False)]

        self.Unpack = Unpack

    def dep_name(self, var, value, type_):
        activation = self.dependency_stack[-1].activation
        variable = activation[var]
        if variable:
            self.dependency_stack[-1].add(Dependency(variable, value, type_))
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
        call = Activation(-1, None, None, path, -1)
        self.activation_stack.append(call)
        return call

    def script_end(self, activation):
        """End script"""
        print("end")

    def call(self, activation, call_id, func, type_):
        """Capture call before"""
        call = Activation(-1, activation, func, func.__name__, call_id)
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
        self.dependency_stack.append(Decorator(-1, name, activation))
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
        """Capture lambda definitions"""
        call = self.activation_stack[-1]
        if id(call.func) != id(me_func):
            return call
        call.with_definition = True
        call.definition_activation = definition_activation
        parameters = self._match_arguments(call, *parameters)
        return value

    def comprehension(self, type_, definition_activation, dep_type, lambda_,):
        """Capture comprehension"""
        call = Activation(-1, definition_activation, lambda_, type_, -1)
        call.dependency_type = dep_type
        self.dependency_stack.append(call)
        self.activation_stack.append(call)
        self.dependency_stack.pop()
        result = lambda_(lambda_, definition_activation, call)
        print(call, [a for a in call.dependencies])
        self.dependency_stack[-1].add(Dependency(
            call, result, dep_type
        ))
        self.activation_stack.pop()
        return result

    def comp_elt(self, activation, arg):
        """Capture comprehension value before"""
        self.dependency_stack.append(ComprehensionResult(activation, arg))
        return self._comp_elt

    def _comp_elt(self, value):
        """Capture comprehension value after"""
        comp_result = self.dependency_stack.pop()
        comp_result.value = value
        activation = comp_result.activation
        for dep in activation.delay_conditions:
            comp_result.add(dep)
        activation.delay_conditions = []
        print(comp_result, [a for a in comp_result.dependencies])
        if activation.name == "GenExpr":
            activation.last_yield = Dependency("yield", value, "direct")
        else:
            activation.add(Dependency(
                "yield", comp_result, "direct"
            ))

        return value

    def comp_condition(self, activation):
        """Capture comprehension condition before"""
        self.dependency_stack.append(ComprehensionCondition(activation))
        return self._comp_condition

    def _comp_condition(self, value):
        """Capture comprehension condition after"""
        comp_cond = self.dependency_stack.pop()
        comp_cond.value = value
        activation = comp_cond.activation
        activation.delay_conditions.append(Dependency(
            "<condition>", comp_cond, "conditional"
        ))
        return value

    def list(self, activation):
        """Capture list/tuple before"""
        self.dependency_stack.append(OrderedDependencyAware(activation))
        return self._list

    def _list(self, value):
        """Capture list/tuple after"""
        list_ = self.dependency_stack.pop()
        self.dependency_stack[-1].add(list_)
        return value

    def element(self, activation):
        self.dependency_stack.append(DependencyAware(activation))
        return self._element

    def _element(self, value):
        element = self.dependency_stack.pop()
        self.dependency_stack[-1].add(element)
        return value

    def iterable(self, activation, unpack):
        """Capture iterable before"""
        self.dependency_stack.append(Iterable(activation, unpack))
        return self._iterable

    def _iterable(self, value):
        """Capture iterable after"""
        iterable = self.dependency_stack.pop()
        iterable.value = value
        activation = iterable.activation
        activation.add(Dependency(
            "<iterable>", iterable, "direct"
        ))
        return self.iterator(activation, iterable, value)

    def unpack(self, activation, unpack, dependency):
        print(unpack)
        return True
        if unpack.type == "Name":
            print("new var:", unpack, dependency)
            return target
        target, new_target = tee(value)

        for tup, val in zip(unpack_tuple, new_value):
            self.unpack(activation, )
        return value
        self.unpack(activation,)
        try:
            iter(value)
        except TypeError:
            print("new_var", u)
        else:

            pass

    def iterator(self, activation, dep, old_iterable):
        """Capture iteration"""
        unpack = dep.unpack
        for value in old_iterable:
            self.unpack(activation, unpack, dep)
            yield value

    def assign_value(self, activation):
        """Capture assignment values before"""
        self.dependency_stack.append(Assignment(activation))
        return self._assign_value

    def _assign_value(self, value):
        """Capture assignment values after"""
        assignment = self.dependency_stack.pop()
        assignment.value = value
        assignment.activation.last_assignment.append(assignment)
        return value

    def pop_assign(self, activation):
        """Return assignment value dependencies"""
        return activation.last_assignment.pop()

    def new_var(self, activation, var, value, type_):
        """Create new variable"""
        variable = Variable(-1, activation, var, value, type_)
        activation[var] = variable
        return variable

    def new_dependency(self, variable, dependency, type_, mode):
        if mode == "bindto":
            # Share parts
            variable.parts = dependency.parts
        print(variable, "<-", dependency, type_, mode)

    def dependency_or_bind(self, variable, dependencies, type_):
        for dependency in dependencies:
            if isinstance(dependency, Dependency):
                dep = dependency.variable
                if (dep.value_id != variable.value_id) or dep.immutable:
                    self.new_dependency(variable, dep, type_, "dependency")
                else:
                    self.new_dependency(variable, dep, type_, "bindto")
            elif isinstance(dependency, DependencyAware):
                self.dependency_or_bind(variable, dependency.dependencies,
                                        type_)
            else:
                print("DEPENDENCY", type(dependency).__name__)


    def assign(self, activation, assign, unpack, value):
        """Create variables for assignment"""
        if unpack.type == "Name":
            variable = self.new_var(activation, unpack.var, value, "normal")
            self.dependency_or_bind(variable, assign.dependencies, "direct")

        else:
            print(unpack, value)
