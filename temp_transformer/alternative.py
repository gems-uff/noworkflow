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
    """Create __noworkflow__.<name>(args...) call"""
    return call(
        ast.Attribute(ast.Name("__noworkflow__", L()), name, L()),
        args, keywords, star, kwargs
    )


def double_noworkflow(name, args, keywords=None, star=None, kwargs=None):
    """Create __noworkflow__.<name>()(args...) call"""
    return call(
        noworkflow(name, []),
        args, keywords, star, kwargs
    )

class RewriteDependencies(ast.NodeTransformer):

    def visit_Name(self, node):
        return ast.copy_location(
            noworkflow("dep_name", [ast.Str(node.id)]),
            node
        )


class RewriteAST(ast.NodeTransformer):

    def __init__(self, code):
        self.lcode = code.split("\n")
        self.call_id = 0
        self.dependency_rewriter = RewriteDependencies()

    def extract_str(self, node, template="{}"):
        """Create Str node with node content"""
        return ast.Str(template.format(
            pyposast.extract_code(self.lcode, node)
        ))

    def _call_arg(self, node, star, call_id):
        if not node:
            return None
        star_node = true() if star else false()
        return double_noworkflow("arg", [
            self.dependency_rewriter.visit(node), star_node, ast.Num(call_id)
        ])

    def _call_keyword(self, arg, value, call_id):
        if not value:
            return None
        return double_noworkflow("keyword", [
            self.dependency_rewriter.visit(value),
            ast.Str(arg) if arg else ast.Str("**"),
            ast.Num(call_id)
        ])

    def process_call_arg(self, node, call_id):
        """Process call argument. Create __noworkflow__.arg()(arg)"""
        if PY3 and isinstance(node, ast.Starred):
            result = ast.Starred(self._call_arg(node.value, True, call_id),
                                 node.ctx)
        else:
            result = self._call_arg(node, False, call_id)
        return ast.copy_location(result, node)

    def process_call_keyword(self, node, call_id):
        return ast.copy_location(ast.keyword(node.arg, self._call_keyword(
            node.arg, node.value, call_id
        )), node)

    def process_arg(self, arg):
        """Return string with arg name, or None object"""
        if PY3:
            return none() if not arg else ast.Str(arg.arg)
        return none() if not arg else self.extract_str(arg)

    def process_arguments(self, arguments):
        """Return list of arguments for __noworkflow__.function_def"""
        args = ast.List([self.process_arg(arg) for arg in arguments.args], L())
        vararg = self.process_arg(arguments.vararg)
        kwarg = self.process_arg(arguments.kwarg)
        if PY3:
            kwonlyargs = ast.List([
                self.process_arg(arg) for arg in arguments.kwonlyargs
            ], L())
        else:
            kwonlyargs = none()
        return [args, vararg, kwarg, kwonlyargs]


    def visit_Call(self, node):                                                  # pylint: disable=invalid-name
        """Visit Call.
        Replace f(x, *y, **z) to __noworkflow__.call("f", f, x, *y, **z)
        """
        cid = self.call_id
        self.call_id += 1

        args = [
            ast.Num(cid), node.func
        ] + [self.process_call_arg(arg, cid) for arg in node.args]

        keywords = [self.process_call_keyword(key, cid)
                    for key in node.keywords]

        kwargs = {}
        if not PY35:
            kwargs = {
                "star": self._call_arg(node.starargs, True, cid),
                "kwargs": self._call_keyword(None, node.kwargs, cid),
            }
        new_node = ast.copy_location(
            noworkflow("call", args, keywords=keywords, **kwargs
        ), node)

        return ast.fix_missing_locations(new_node)

    def visit_FunctionDef(self, node):                                           # pylint: disable=invalid-name
        node.body.insert(0, ast.Expr(noworkflow(
            "function_def", self.process_arguments(node.args)
        )))
        return ast.fix_missing_locations(node)


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
tree = RewriteAST(code).visit(tree)

compiled = compile(tree, path, 'exec')
eval(compiled, namespace)