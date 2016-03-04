import sys
import ast
import pyposast
from now import ExecutionCollector


PY35 = sys.version_info >= (3, 5)
PY3 = sys.version_info >= (3, 0)

import sys
path = ' '.join(sys.argv[1:])
path = path or "test.py"


def L():                                                                         # pylint: disable=invalid-name
    return ast.Load()


def S():                                                                         # pylint: disable=invalid-name
    return ast.Store()


def P():                                                                         # pylint: disable=invalid-name
    return ast.Param()


def none():
    if PY3:
        return ast.NameConstant(None)
    return ast.Name("None", L())


def true():
    if PY3:
        return ast.NameConstant(True)
    return ast.Name("True", L())


def false():
    if PY3:
        return ast.NameConstant(False)
    return ast.Name("False", L())


def call(func, args, keywords=None, star=None, kwargs=None):
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
    """Create <now>.<name>()(args...) call"""
    return call(
        noworkflow(name, external_args),
        args, keywords, star, kwargs
    )


def activation():
    return ast.Name("__now_activation__", L())


def param(value, annotation=None):
    if PY3:
        return ast.arg(value, annotation)
    return ast.Name(value, P())


class ReplaceContextWithLoad(ast.NodeTransformer):
    """Replace expr_context from any node to Load context"""

    def visit_Attribute(self, node):
        """Visit Attribute"""
        return ast.copy_location(ast.Attribute(
            self.visit(node.value), node.attr, L()
        ), node)

    def visit_Subscript(self, node):
        """Visit Subscript"""
        return ast.copy_location(ast.Subscript(
            self.visit(node.value), self.visit(node.slice), L()
        ), node)

    def visit_Name(self, node):
        """Visit Name"""
        return ast.copy_location(ast.Name(
            node.id, L()
        ), node)

    def visit_List(self, node):
        """Visit List"""
        return ast.copy_location(ast.List(
            [self.visit(elt) for elt in node.elts], L()
        ), node)

    def visit_Tuple(self, node):
        """Visit Tuple"""
        return ast.copy_location(ast.Tuple(
            [self.visit(elt) for elt in node.elts], L()
        ), node)





class RewriteAST(ast.NodeTransformer):

    def __init__(self, path, code):
        self.path = path
        self.code = code
        self.lcode = code.split("\n")
        self.call_id = 0
        self.to_load = ReplaceContextWithLoad()
        self._dependency_type = "direct"

# --- util

    def dependency_type(self):
        """Return Str(self.dependency_type)"""
        return ast.Str(self._dependency_type)

    def capture(self, node, mode="direct"):
        """Capture dependencies from node"""
        dependency_rewriter = RewriteDependencies(self.path, self.code)
        return dependency_rewriter.visit(node, mode=mode)

    def extract_str(self, node, template="{}"):
        """Create Str node with node content"""
        return ast.Str(template.format(
            pyposast.extract_code(self.lcode, node)
        ))

# --- mod

    def process_script(self, node, cls):
        """Process script, creating initial activation, and closing it"""
        body = self.process_body(node.body)

        body.insert(0, ast.Assign(
            [ast.Name("__now_activation__", S())],
            noworkflow("script_start", [ast.Str(self.path)])
        ))
        body.append(ast.Expr(noworkflow(
            "script_end", [ast.Name("__now_activation__", L())]
        )))
        return ast.copy_location(cls(body), node)

    def process_body(self, body):
        """Process statement list"""
        return [self.visit(stmt) for stmt in body]

    def visit_Module(self, node):                                                # pylint: disable=invalid-name
        """Visit Module. Create and close activation"""
        return ast.fix_missing_locations(self.process_script(node, ast.Module))

    def visit_Interactive(self, node):                                           # pylint: disable=invalid-name
        """Visit Interactive. Create and close activation"""
        return ast.fix_missing_locations(
            self.process_script(node, ast.Interactive))

    # ToDo: visit_Expression?

# --- stmt

    def process_arg(self, arg):
        """Return None if arg does not exist
        Otherwise, return tuple ("arg name", value)
        """
        if not arg:
            return none()
        if PY3:
            arg = arg.arg
        if isinstance(arg, str):
            return ast.Tuple([ast.Str(arg), ast.Name(arg, L())], L())
        return ast.Tuple([self.extract_str(arg), self.to_load.visit(arg)], L())

    def process_default(self, default):
        """Process default value"""
        if not default:
            return none()
        return double_noworkflow("default", [], [
            self.capture(default)
        ])

    def process_arguments(self, arguments):
        """Return List of arguments for <now>.function_def"""
        args = ast.List([self.process_arg(arg) for arg in arguments.args], L())
        vararg = self.process_arg(arguments.vararg)
        defaults = ast.List([
            self.process_default(def_) for def_ in arguments.defaults
        ], L())
        kwarg = self.process_arg(arguments.kwarg)
        if PY3:
            kwonlyargs = ast.List([
                self.process_arg(arg) for arg in arguments.kwonlyargs
            ], L())
        else:
            kwonlyargs = none()
        return [args, defaults, vararg, kwarg, kwonlyargs]

    def process_decorator(self, decorator):
        """Transform @dec into @__noworkflow__.decorator(<act>)(|dec|)"""
        return ast.copy_location(double_noworkflow(
            "decorator", [self.extract_str(decorator), activation()],
            [self.capture(decorator)]
        ), decorator)

    def visit_FunctionDef(self, node, cls=ast.FunctionDef):                      # pylint: disable=invalid-name
        """Visit FunctionDef.
        Transform:
        @dec
        def f(x, y=2, *args, z=3, **kwargs):
            ...
        Into:
        @<now>.decorator(__now_activation__)(|dec|)
        @<now>.function_def_decorator(__now_activation__)
        def f(__now_me_func__, __now_parent__, x, y=2, *args, z=3, **kwargs):
            __now_activation__ = <now>.function_def(
                __now_me_func__, __now_parent__, <arguments>
            )
            ...
        """
        decorators = [self.process_decorator(dec)
                      for dec in node.decorator_list]
        decorators.append(noworkflow(
            "function_def_decorator", [ast.Name("__now_activation__", L())]
        ))

        body = [self.visit(stmt) for stmt in node.body]
        body.insert(0, ast.Assign(
            [ast.Name("__now_activation__", S())], noworkflow(
                "function_def", [
                    ast.Name("__now_me_func__", L()),
                    ast.Name("__now_parent__", L()),
                ] + self.process_arguments(node.args)
            )
        ))
        node.args.args = [
            param("__now_me_func__"), param("__now_parent__")
        ] + node.args.args

        constructor = [node.name, node.args, body, decorators]
        if PY3:
            constructor.append(node.returns)

        return ast.copy_location(cls(*constructor), node)

    def visit_AsyncFunctionDef(self, node):                                      # pylint: disable=invalid-name
        """Visit AsyncFunctionDef. Same transformations as FunctionDef"""
        return self.visit_FunctionDef(node, cls=ast.AsyncFunctionDef)

# --- expr

    def _call_arg(self, node, star, call_id):
        """Create <now>.arg(<act>, star, call_id)(|node|)"""
        if not node:
            return None
        star_node = true() if star else false()
        return double_noworkflow(
            "arg",
            [activation(), star_node, ast.Num(call_id)],
            [self.capture(node)]
        )

    def _call_keyword(self, arg, value, call_id):
        """Create <now>.keyword(<act>, star, call_id)(|node|)"""
        if not value:
            return None
        return double_noworkflow(
            "keyword", [
                activation(),
                ast.Str(arg) if arg else ast.Str("**"), ast.Num(call_id)
            ], [self.capture(value)]
        )

    def process_call_arg(self, node, call_id):
        """Process call argument
        Transform (star?)value into <now>.arg(star?, call_id)(value)
        """
        if PY3 and isinstance(node, ast.Starred):
            result = ast.Starred(self._call_arg(node.value, True, call_id),
                                 node.ctx)
        else:
            result = self._call_arg(node, False, call_id)
        return ast.copy_location(result, node)

    def process_call_keyword(self, node, call_id):
        """Process call keyword
        Transform arg=val into arg=<now>.keyword(arg, call_id)(value)
        """
        return ast.copy_location(ast.keyword(node.arg, self._call_keyword(
            node.arg, node.value, call_id
        )), node)

    def visit_Call(self, node):                                                  # pylint: disable=invalid-name
        """Visit Call.
        Replace f(x, *y, **z) to <now>.call(<act>, cid, f, <dep>)(x, *y, **z)
        """
        cid = self.call_id
        self.call_id += 1

        node.func = ast.copy_location(noworkflow("call", [
            activation(), ast.Num(cid), node.func, self.dependency_type()
        ]), node.func)

        node.args = [self.process_call_arg(arg, cid) for arg in node.args]
        node.keywords = [self.process_call_keyword(k, cid)
                         for k in node.keywords]

        if not PY35:
            node.starargs = self._call_arg(node.starargs, True, cid)
            node.kwargs = self._call_keyword(None, node.kwargs, cid)

        return ast.fix_missing_locations(node)

    def visit_Lambda(self, node):                                                # pylint: disable=invalid-name
        """Visit Lambda
        Transform:
            lambda args: result
        into:
        <now>.function_def_decorator(__now_activation__)(
            lambda __now_me_func__, __now_parent__, args:
                <now>.lambda_def(__now_me_func__, __now_parent__, args)(result)
        )
        """
        node.body = noworkflow(
            "lambda_def", [
                ast.Name("__now_me_func__", L()),
                ast.Name("__now_parent__", L()),
                self.visit(node.body)
            ] + self.process_arguments(node.args)
        )
        node.args.args = [
            param("__now_me_func__"), param("__now_parent__"),
        ] + node.args.args
        return ast.copy_location(double_noworkflow(
            "function_def_decorator",
            [activation()], [node]
        ), node)

    def visit_comprehension(self, node):
        """Visit comprehension"""
        return ast.copy_location(ast.comprehension(
            node.target,
            node.iter,
            [double_noworkflow(
                "comp_condition",
                [activation()],
                [self.capture(if_, "conditional")]
             ) for if_ in node.ifs]
        ), node)

        return ast.copy_location(ast.comprehension(
            node.target,
            double_noworkflow(
                "iterable",
                [activation(), self.extract_unpack(node.iter)],
                [node.iter]
            ), [double_noworkflow(
                "comp_condition",
                [activation()],
                [self.capture(if_, "conditional")]
             ) for if_ in node.ifs]
        ), node)

    def visit_ListComp(self, node, cls=ast.ListComp):                            # pylint: disable=invalid-name
        """Visit ListComp
        Transform:
            [x + y for x in iterable if z]
        Into:
            Transform <(lambda: [x + y for x in iterable if z])()>

        ? Alternative ToDo:
            <now>.comprehension(<cls>, <act>, <type>,
                lambda <me>, <parent>, <act>: [
                    <now>.comp_elt(<act>, "x + y")(|x + y|)
                    for x in <now>.iterable(<act>, "x")(|iterable|))
                    if <now>.comp_condition(<act>)(|z|)
                ]
            )
        """
        #ToDo
        lambda_args = [[
            param("__now_me_func__"),
            param("__now_parent__"),
            param("__now_activation__")
        ], None]
        if PY3:
            lambda_args += [[], []]
        lambda_args += [None, []]
        new_node = ast.copy_location(noworkflow(
            "comprehension", [
                ast.Str(cls.__name__),
                activation(),
                self.dependency_type(),
                ast.Lambda(
                    ast.arguments(*lambda_args),
                    cls(double_noworkflow(
                        "comp_elt",
                        [activation(), self.extract_str(node.elt)],
                        [self.capture(node.elt)]
                    ), [self.visit_comprehension(gen) for gen in node.generators])
                )]
        ), node)

        return new_node

    def visit_SetComp(self, node):                                               # pylint: disable=invalid-name
        """Visit SetComp. Similar to ListComp"""
        return self.visit_ListComp(node, cls=ast.SetComp)

    def visit_List(self, node, cls=ast.List):                                    # pylint: disable=invalid-name
        """Visit List
        Transform:
            [a, 2, 3]
        Into:
            <now>.list(<act>, [
                <now>.element(<act>)(a),
                <now>.element(<act>)(2),
                <now>.element(<act>)(3),
            ])
        """
        if isinstance(node.ctx, ast.Store):
            return node
        return ast.copy_location(double_noworkflow("list", [activation()], [
            cls(
                [double_noworkflow(
                    "element", [activation()], [self.capture(elt)]
                ) for elt in node.elts],
                node.ctx
            )
        ]), node)

    def visit_Tuple(self, node):                                                 # pylint: disable=invalid-name
        """Visit Tuple. Similar to List"""
        print(node.ctx)
        return self.visit_List(node, cls=ast.Tuple)


class RewriteDependencies(RewriteAST):

    def visit_Name(self, node):                                                  # pylint: disable=invalid-name
        """Visit Name"""
        return ast.copy_location(noworkflow(
            "dep_name", [ast.Str(node.id), node, self.dependency_type()]
        ), node)

    def visit_Lambda(self, node):                                                # pylint: disable=invalid-name
        """Visit Lambda"""
        return ast.copy_location(noworkflow("dep_name", [
            self.extract_str(node),
            super(RewriteDependencies, self).visit_Lambda(node),
            self.dependency_type()
        ]), node)

    def visit_IfExp(self, node):                                                # pylint: disable=invalid-name
        """Visit IfExp"""
        return ast.copy_location(ast.IfExp(
            self.capture(node.test, mode="conditional"),
            self.visit(node.body),
            self.visit(node.orelse)
        ), node)

    def visit(self, node, mode="direct"):
        """Visit node"""
        self._dependency_type = mode
        return super(RewriteDependencies, self).visit(node)

builtin = __builtins__
builtin.__noworkflow__ = ExecutionCollector()

namespace = {
    '__name__'    : '__main__',
    '__file__'    : path,
    '__builtins__': builtin,
}

with open(path, "rb") as script_file:
    code = pyposast.native_decode_source(script_file.read())
tree = pyposast.parse(code, path)
tree = RewriteAST(path, code).visit(tree)

compiled = compile(tree, path, 'exec')
eval(compiled, namespace)