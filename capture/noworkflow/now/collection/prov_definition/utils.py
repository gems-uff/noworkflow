# Copyright (c) 2016 Universidade Federal Fluminense (UFF)
# Copyright (c) 2016 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""Helpers for AST analysis"""
from __future__ import (absolute_import, print_function,
                        division, unicode_literals)

import ast
import sys
import itertools

from collections import namedtuple

from future.utils import viewvalues


CallDependency = namedtuple("Call", "line col")
ReturnDependency = namedtuple("Return", "line col")


class Variable(object):                                                          # pylint: disable=too-few-public-methods
    """Represent a variable name"""

    def __init__(self, name, typ):
        self.name = name
        self.type = typ

    def __hash__(self):
        return hash(self.name)

    def __eq__(self, other):
        if isinstance(other, str):
            return self.name == other
        elif isinstance(other, Variable):
            return self.name == other.name
        return False

    def __repr__(self):
        return "Var({}, {})".format(self.name, self.type)


class Dependency(object):                                                        # pylint: disable=too-few-public-methods
    """Represent a variable dependency"""

    def __init__(self, dependency, typ):
        self.dependency = dependency
        self.type = typ

    def __hash__(self):
        return hash(self.dependency)

    def __eq__(self, other):
        if not isinstance(other, Dependency):
            return False
        return self.dependency == other.dependency and self.type == other.type

    def __repr__(self):
        return "Dependency({}, {})".format(self.dependency, self.type)


def variable(name, typ):
    """Create Variable or Call Dependency"""
    if isinstance(name, str):
        return Variable(name, typ)
    if isinstance(name, (Variable, ReturnDependency, CallDependency)):
        return name
    if typ == "return":
        return ReturnDependency(*name)
    if typ in ("call", "print", "import", "import from"):
        return CallDependency(*name)
    return Variable(name, typ)


class NamedContext(object):
    """Store variable visibility context"""

    def __init__(self):
        self._names = [set()]
        self.use = False

    def flat(self):
        """Return available variable in the current context"""
        result = set()
        for name in self._names:
            result = result.union(name)
        return result

    def enable(self):
        """Enable variable collection"""
        self.use = True
        self._names.append(set())

    def disable(self):
        """Disable variable collection"""
        self.use = False

    def pop(self):
        """Remove sub-context from stack"""
        self._names.pop()

    def add(self, name):
        """Add variable to context"""
        if self.use:
            self._names[-1].add(name)


class DefinitionObject(object):

    def __repr__(self):
        return "{}({})".format(self.__class__.__name__, self.info())

    def _dependencies(self, node, visitor_class, func):                          # pylint: disable=no-self-use
        """Extract name dependencies from node"""
        visitor = visitor_class()
        visitor.visit(node)
        return [func(x if isinstance(x, FunctionCall) else x[0])
                for x in visitor.names]


class Loop(DefinitionObject):
    """Loop class. Used for For and While nodes"""

    def __init__(self, node, typ):
        self.node = node
        self.first_line = node.first_line
        self.last_line = node.last_line
        self.type = typ
        self.iterable = []
        self.iter_var = []
        self.maybe_call = None

    def info(self):
        """Return call information"""
        result = ("first_line={}, last_line={}")
        return result.format(self.first_line, self.last_line)

    def add_iterable(self, node, visitor_class):
        """Extract dependencies from iterable"""
        self.iterable = self._dependencies(
            node, visitor_class, lambda x: Dependency(x, "direct"))

    def add_iter_var(self, node, visitor_class):
        """Extract dependencies from iterable"""
        self.iter_var = self._dependencies(
            node, visitor_class, lambda x: Variable(x, "normal"))


class Condition(DefinitionObject):
    """Loop class. Used for If and While nodes"""

    def __init__(self, node):
        self.node = node
        self.first_line = node.first_line
        self.last_line = node.last_line
        self.test_var = []
        self.has_return = False

    def info(self):
        """Return call information"""
        result = ("first_line={}, last_line={}")
        return result.format(self.first_line, self.last_line)

    def add_test(self, node, visitor_class):
        """Extract dependencies from iterable"""
        self.test_var += self._dependencies(
            node, visitor_class, lambda x: Dependency(x, "conditional"))


class FunctionCall(ast.NodeVisitor):                                             # pylint: disable=too-many-instance-attributes
    """Represent a function call"""

    def __init__(self, visitor_class):
        self.self_attr = []
        self.func = []
        self.args = []
        self.keywords = {}
        self.starargs = []
        self.kwargs = []
        self.result = None
        self.line = -1
        self.col = -1
        self.visitor_class = visitor_class
        self.name = ""
        self.prefix = "call"

    def all_args(self):
        """List arguments of function call"""
        return [
            Dependency(x, "parameter")
            for x in itertools.chain(
                self.self_attr,
                itertools.chain.from_iterable(self.args),
                self.starargs,
                self.kwargs,
                itertools.chain.from_iterable(viewvalues(self.keywords))
            )
        ]

    def use_visitor(self, node):
        """Use configured visitor to visit sub node"""
        visitor = self.visitor_class()
        visitor.visit(node)
        return [x if isinstance(x, FunctionCall) else x[0]
                for x in visitor.names]

    def visit_Call(self, node):                                                  # pylint: disable=invalid-name
        """Visit Call"""
        self.func = self.use_visitor(node.func)
        if isinstance(node.func, ast.Attribute):
            self.self_attr = self.use_visitor(node.func.value)
        self.args = []
        for arg in node.args:
            if sys.version_info <= (3, 4) or not isinstance(arg, ast.Starred):
                self.args.append(self.use_visitor(arg))
            else:
                self.visit(arg)
        for keyword in node.keywords:
            self.visit(keyword)
        if hasattr(node, "starargs"):
            # Python <= 3.4
            if node.starargs:
                self.starargs = self.use_visitor(node.starargs)
            if node.kwargs:
                self.kwargs = self.use_visitor(node.kwargs)

    def visit_Starred(self, node):                                               # pylint: disable=invalid-name
        """Visit Starred. Only valid in Call context after Python 3.5"""
        # Python 3.5
        self.starargs += self.use_visitor(node)

    def visit_keyword(self, node):
        """Visit keyword"""
        if node.arg:
            self.keywords[node.arg] = self.use_visitor(node.value)
        else:
            # Python 3.5
            self.kwargs += self.use_visitor(node.value)

    def info(self):
        """Return call information"""
        result = ("line={}, col={}, "
                  "func={}, args={}, keywords={}, *args={}, **kwargs={}")
        return result.format(self.line, self.col, self.func, self.args,
                             self.keywords, self.starargs, self.kwargs)

    def __repr__(self):
        return "F({})".format(self.info())


class ClassDef(FunctionCall):
    """Represent a class definition"""

    def __repr__(self):
        return "Class(line={}, col={})".format(self.line, self.col)


class Decorator(FunctionCall):
    """Represent a decorator"""

    def __init__(self, *args, **kwargs):
        super(Decorator, self).__init__(*args, **kwargs)
        self.is_fn = True

    def __repr__(self):
        return "Decorator({})".format(self.info())

    def visit_Name(self, node):                                                  # pylint: disable=invalid-name
        """Visit Name"""
        self.func = self.use_visitor(node)
        self.is_fn = False

    def info(self):
        """Return decorator information"""
        if self.is_fn:
            return super(Decorator, self).info()
        return "line={}, col={}, name={}".format(
            self.line, self.col, self.func)


class Generator(FunctionCall):
    """Represent a generator"""

    def __init__(self, *args, **kwargs):
        self.type = args[-1]
        args = args[:-1]
        super(Generator, self).__init__(*args, **kwargs)

    def __repr__(self):
        return "Generator({})".format(self.info())

    def info(self):
        """Return generator information"""
        return "line={}, col={}, type={}".format(
            self.line, self.col, self.type)


class GeneratorCall(Generator):
    """Represent a generator call
    CALL_FUNCTION for set and dict comprehension on Python 2 and Python 3
    CALL_FUNCTION for list comprehension on Python 3
    """

    def __repr__(self):
        return "GeneratorCall({})".format(self.info())


class Assert(FunctionCall):
    """Represent an assert"""

    def __init__(self, *args, **kwargs):
        self.msg = args[-1]
        args = args[:-1]
        super(Assert, self).__init__(*args, **kwargs)

    def __repr__(self):
        return "Assert({})".format(self.info())

    def info(self):
        """Return assert information"""
        return "line={}, col={}, msg={}".format(
            self.line, self.col, self.msg)


class Print(FunctionCall):
    """Represent a print statement"""

    def __init__(self, *args, **kwargs):
        super(Print, self).__init__(*args, **kwargs)

    def __repr__(self):
        return "Print({})".format(self.info())


class With(FunctionCall):
    """Represent a with"""

    def __repr__(self):
        return "With({})".format(self.info())

    def info(self):
        """Return with information"""
        return "line={}, col={}".format(
            self.line, self.col)


class Import(FunctionCall):
    """Represent an import statement"""

    def __init__(self, *args, **kwargs):
        super(Import, self).__init__(*args, **kwargs)
        self.prefix = "import"

    def __repr__(self):
        return "Import(line={})".format(self.line)


class ForIter(FunctionCall):
    """Represent a for iter"""

    def __init__(self, *args, **kwargs):
        super(ForIter, self).__init__(*args, **kwargs)
        self.prefix = "iterator"

    def __repr__(self):
        return "ForIter({})".format(self.info())

    def info(self):
        """Return ForIter information"""
        return "line={}, col={}".format(
            self.line, self.col)


def index(lis, alternatives):
    """Return index of one of the <alternatives> in <lis>"""
    for alt in alternatives:
        try:
            return lis.index(alt)
        except ValueError:
            pass
    return None


def safeget(container, ind):
    """Try to access element in container. If it fails, prints container"""
    try:
        return container[ind]
    except IndexError as err:
        if not err.args:
            err.args = ("",)
        import pprint
        err.args = (err.args[0] + "\n Get\n  Index {}\n  Container \n{}".format(
            ind, pprint.pformat(list(enumerate(container)))),) + err.args[1:]
        raise err
