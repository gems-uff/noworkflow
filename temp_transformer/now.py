from __future__ import (absolute_import, print_function,
                        division, unicode_literals)

from collections import OrderedDict
from future.utils import viewvalues, viewkeys, viewitems
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

    def __init__(self, activation):
        super(OrderedDependencyAware, self).__init__(activation)
        self.parts = []

    def item(self, dependency):
        """Add item dependency"""
        if self.active:
            self.parts.append(dependency)

    def __iter__(self):
        return enumerate(self.parts)

    @classmethod
    def iterate_value(cls, value):
        """Get parts of value"""
        return enumerate(value)

class SetDependencyAware(DependencyAware):

    def __init__(self, activation):
        super(SetDependencyAware, self).__init__(activation)
        self.parts = {}

    def item(self, dependency):
        """Add item dependency"""
        if self.active:
            value = dependency.value
            hash_ = "<%r>" % (hash(value),)
            self.parts[hash_] = dependency

    def __iter__(self):
        return iter(viewitems(self.parts))

    @classmethod
    def iterate_value(cls, value):
        """Get parts of value"""
        return (("<%r>" % (hash(x),), x)
                for x in value)

class DictDependencyAware(DependencyAware):

    def __init__(self, activation):
        super(DictDependencyAware, self).__init__(activation)
        self.parts = {}
        self._keys = []

    def key(self, key):
        """Add key value"""
        self._keys.append(key)

    def value(self, dependency):
        """Associate key to dependency"""
        key = self._keys.pop()
        if self.active:
            self.parts[key] = dependency

    def __iter__(self):
        return iter(viewitems(self.parts))

    @classmethod
    def iterate_value(cls, value):
        """Get parts of value"""
        return iter(viewitems(value))

class ElementDependency(DependencyAware):

    def __init__(self, activation):
        super(ElementDependency, self).__init__(activation)
        self.value = None

SPECIAL_DATA_STRUCTURES = (
    ((tuple, list), OrderedDependencyAware),
    (dict, DictDependencyAware),
    (set, SetDependencyAware),
)

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


class Subscript(DependencyAware):
    """Represent a Subscript"""

    def __init__(self, activation, subscript_id, value=None):
        super(Subscript, self).__init__(activation)
        self.value = value
        self.subscript_id = subscript_id

    def __repr__(self):
        return "{}".format(self.value)


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

    def set(self, activation):
        """Capture list/tuple before"""
        self.dependency_stack.append(SetDependencyAware(activation))
        return self._set

    def _set(self, value):
        """Capture list/tuple after"""
        set_ = self.dependency_stack.pop()
        self.dependency_stack[-1].add(set_)
        return value

    def element(self, activation):
        """Capture list element before"""
        self.dependency_stack.append(ElementDependency(activation))
        return self._element

    def _element(self, value):
        """Capture list element after"""
        element = self.dependency_stack.pop()
        element.value = value
        self.dependency_stack[-1].item(element)
        return value

    def dict(self, activation):
        """Capture dict before"""
        self.dependency_stack.append(DictDependencyAware(activation))
        return self._dict

    def _dict(self, value):
        """Capture list/tuple after"""
        dict_ = self.dependency_stack.pop()
        self.dependency_stack[-1].add(dict_)
        return value

    def dict_key(self, activation):
        """Capture dict key before"""
        self.dependency_stack.append(DependencyAware(activation))
        return self._dict_key

    def _dict_key(self, value):
        """Capture dict key after"""
        element = self.dependency_stack.pop()
        self.dependency_stack[-1].add(element)
        self.dependency_stack[-1].key(value)
        return value

    def dict_value(self, activation):
        """Capture dict value before"""
        self.dependency_stack.append(ElementDependency(activation))
        return self._dict_value

    def _dict_value(self, value):
        """Capture dict value after"""
        element = self.dependency_stack.pop()
        element.value = value
        self.dependency_stack[-1].value(element)
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

    def single_dependency_or_bind(self, variable, dependency, type_):
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

    def dependency_or_bind(self, variable, dependencies, type_):
        # Create dependency of bind
        name = variable.name
        activation = variable.activation
        var_type = variable.type
        for cls, dep_cls in SPECIAL_DATA_STRUCTURES:
            if isinstance(variable.value, cls):
                if len(dependencies) == 1:
                    # Single Dependency. Check if match single dependency type
                    dependency0 = dependencies[0]
                    if isinstance(dependency0, dep_cls):
                        if dependency0.dependencies:
                            self.dependency_or_bind(
                                variable, dependency0.dependencies, type_
                            )
                        # Create each part
                        for key, dependency in dependency0:
                            part = Variable(-1, activation,
                                            "%s[%r]" % (name, key),
                                            dependency.value, var_type)
                            variable.parts["[%r]" % (key,)] = part
                            self.new_dependency(variable, part, type_, "parts")
                            self.dependency_or_bind(
                                part, dependency.dependencies, type_
                            )
                        return
                # ToDo: Create parts?
                #    elif isinstance(dependency0, Dependency):
                #        # Check bind
                #        dep = dependency0.variable
                #        if dep.value_id == variable.value_id and not dep.immutable:
                #            self.new_dependency(variable, dep, type_, "bindto")
                #            return
                #for key, value in dep_cls.iterate_value(variable.value):
                #    part = Variable(-1, activation,
                #                    "%s[%r]" % (name, key),
                #                    value, variable.type)
                #    variable.parts["[%r]" % (key,)] = part
                #    self.new_dependency(variable, part, type_, "parts")
                #    self.dependency_or_bind(part, dependencies, type_)
                #return

        # Variable is not list nor tuple
        for dependency in dependencies:
            self.single_dependency_or_bind(variable, dependency, type_)

    def assign_item(self, activation, assign, unpack, value, item, dep):
        """Create variables for tuple assignment"""
        if dep is not None:
            # dep is OrderedDependencyAware
            if isinstance(item, slice):
                new_ordered = OrderedDependencyAware(activation)
                new_ordered.parts = dep.parts[item]
                new_dep = DependencyAware(activation)
                new_dep.add(new_ordered)
            else:
                new_dep = dep.parts[item]
        else:
            new_dep = assign
        self.assign(activation, new_dep, unpack, value[item])


    def assign(self, activation, assign, unpack, value):
        """Create variables for assignment"""
        deps = assign.dependencies
        dep = None
        if len(deps) == 1 and isinstance(deps[0], OrderedDependencyAware):
            dep = deps[0]
        print(unpack)
        if unpack.type == "Name":
            variable = self.new_var(activation, unpack.var, value, "normal")
            self.dependency_or_bind(variable, assign.dependencies, "direct")
        elif unpack.type in ("Tuple", "List"):
            starred = False
            i = 0
            for i, new_unpack in enumerate(unpack.var):
                if new_unpack.type == "Starred":
                    starred = True
                    break
                self.assign_item(activation, assign, new_unpack, value, i, dep)
            if starred:
                k = len(value)
                for j in range(len(unpack.var) - 1, i, -1):
                    k -= 1
                    new_unpack = unpack.var[j]
                    self.assign_item(
                        activation, assign, new_unpack, value, k, dep
                    )
                new_unpack = unpack.var[i].var
                self.assign_item(
                    activation, assign, new_unpack, value, slice(i, k), dep
                )

        else:
            print(unpack, value)

    def subscript(self, activation, subscript_id):
        self.dependency_stack.append(Subscript(activation, subscript_id))
        return self

    def __getitem__(self, item):
        obj, slic = item
        subscript = self.dependency_stack.pop()
        value = obj[slic]
        subscript.value = value
        return value

    
