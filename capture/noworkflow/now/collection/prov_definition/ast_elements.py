# Copyright (c) 2016 Universidade Federal Fluminense (UFF)
# Copyright (c) 2016 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""Helpers to create ast elements"""

import ast

from ...utils.cross_version import PY3, PY35


def maybe(obj, attribute):
    """Return object attribute or None if it does not exist"""
    try:
        return getattr(obj, attribute)
    except AttributeError:
        return None


def L():                                                                         # pylint: disable=invalid-name
    """Create Load expr context"""
    return ast.Load()


def S():                                                                         # pylint: disable=invalid-name
    """Create Store expr context"""
    return ast.Store()


def P():                                                                         # pylint: disable=invalid-name
    """Create Param expr context"""
    return ast.Param()

def context(node):
    """Return node context as string"""
    if not hasattr(node, "ctx"):
        return "r"
    expr_context = node.ctx
    result = "?"
    if isinstance(expr_context, ast.Load):
        result = "r"
    elif isinstance(expr_context, ast.Store):
        result = "w"
    elif isinstance(expr_context, ast.Del):
        result = "d"
    elif isinstance(expr_context, ast.AugLoad):
        result = "r+"
    elif isinstance(expr_context, ast.AugStore):
        result = "w+"
    elif isinstance(expr_context, ast.Param):
        result = "p"
    return result

def none():
    """Create None object"""
    if PY3:
        return ast.NameConstant(None)
    return ast.Name("None", L())


def true():
    """Create True object"""
    if PY3:
        return ast.NameConstant(True)
    return ast.Name("True", L())


def false():
    """Create False object"""
    if PY3:
        return ast.NameConstant(False)
    return ast.Name("False", L())


def call(func, args, keywords=None, star=None, kwargs=None):
    """Create call with args, keywords, star args and kwargs"""
    keywords = keywords or []
    create_call = [func, args, keywords]
    if not PY35:
        create_call += [star, kwargs]
    return ast.Call(*create_call)


def noworkflow(name, args, keywords=None, star=None, kwargs=None):
    """Create <now>.<name>(args...) call"""
    return call(
        ast.Attribute(ast.Name("__noworkflow__", L()), name, L()),
        args, keywords, star, kwargs
    )


def double_noworkflow(name, external_args, args,
                      keywords=None, star=None, kwargs=None):
    """Create <now>.<name>(external_args)(args...) call"""
    return call(
        noworkflow(name, external_args),
        args, keywords, star, kwargs
    )


def activation():
    """Access activation"""
    return ast.Name("__now_activation__", L())


def param(value, annotation=None):
    """Create function definition param"""
    if PY3:
        return ast.arg(value, annotation)
    return ast.Name(value, P())


def function_def(name, args, body, decs, returns=None, cls=ast.FunctionDef):     # pylint: disable=too-many-arguments
    """Create function definition"""
    constructor = [name, args, body, decs]
    if PY3:
        constructor.append(returns)

    return cls(*constructor)


def class_def(name, bases, body, decorators, keywords=None):
    """Create class definition"""
    constructor = [name, bases]
    if PY3:
        constructor.append(keywords)
    constructor.append(body)
    constructor.append(decorators)

    return ast.ClassDef(*constructor)

def try_def(body, handlers, orelse, finalbody, node=None):
    """Create try block"""
    if PY3:
        result = ast.Try(body, handlers, orelse, finalbody)
        return ast.copy_location(result, node) if node else result
    else:
        if handlers or orelse:
            result = ast.TryExcept(body, handlers, orelse)
            body = [ast.copy_location(result, node) if node else result]
        if finalbody:
            result = ast.TryFinally(body, finalbody)
            body = [ast.copy_location(result, node) if node else result]
        return body[-1]
