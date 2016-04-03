# Copyright (c) 2016 Universidade Federal Fluminense (UFF)
# Copyright (c) 2016 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""AST Visitors to capture definition provenance for slicing"""
from __future__ import (absolute_import, print_function,
                        division, unicode_literals)

import ast
import sys

from collections import defaultdict, namedtuple

from ...utils.bytecode.interpreter import CALL_FUNCTIONS, PRINT_ITEMS
from ...utils.bytecode.interpreter import PRINT_NEW_LINES, SETUP_WITH
from ...utils.bytecode.interpreter import WITH_CLEANUP, SETUP_ASYNC_WITH
from ...utils.bytecode.interpreter import IMPORT_NAMES
from ...utils.bytecode.interpreter import FOR_ITERS, GET_ITERS

from .function_visitor import FunctionVisitor
from .utils import NamedContext, FunctionCall, ClassDef, Decorator, Generator
from .utils import Assert, safeget, With, Print, Import, ForIter, GeneratorCall
from .utils import Dependency, variable, Loop, Condition


class AssignLeftVisitor(ast.NodeVisitor):
    """Visit the left side of assignements and collect names"""
    def __init__(self):
        self.names = []
        self.enable = True
        self.last = ""

    def visit_Attribute(self, node):                                             # pylint: disable=invalid-name
        """Create nested names if it is an attribute"""
        self.generic_visit(node)
        if self.enable:
            self.last += "." + node.attr
            if not isinstance(self.last, str):
                self.last = self.last.encode("utf-8")
            self.names.append((self.last, node.ctx, node.lineno))

    def visit_Subscript(self, node):                                             # pylint: disable=invalid-name
        """Disable visitor for slice"""
        self.visit(node.value)
        self.enable = False
        self.visit(node.slice)

    def visit_Name(self, node):                                                  # pylint: disable=invalid-name
        """Collect names"""
        if self.enable:
            self.last = node.id
            self.names.append((self.last, node.ctx, node.lineno))
        self.generic_visit(node)


class AssignRightVisitor(ast.NodeVisitor):
    """Visit the right side of assignements and collect names"""

    def __init__(self):
        self.names = []
        self.special = NamedContext()
        self.line = -1

    def add(self, name, ctx, lineno):
        """Add name to current context"""
        if not self.special.use:
            self.names.append((name, ctx, lineno))
        else:
            self.special.add(name)

    def in_special(self, node):
        """Check if node is in special list for function calls"""
        return node.id in self.special.flat()

    def max_line(self, node):
        """Update the line according to the max lineno found"""
        try:
            self.line = max(node.lineno, self.line)
        except (TypeError, AttributeError):
            pass

    def new_comprehension(self, node):
        """Add call to comprehension"""
        self.max_line(node)
        self.add(variable(node.uid, "call"), "fn", node.lineno)

    def visit_Name(self, node):                                                  # pylint: disable=invalid-name
        """Collect names"""
        self.max_line(node)
        if not self.in_special(node):
            self.add(node.id, node.ctx, node.lineno)
        self.generic_visit(node)

    def visit_Lambda(self, node):                                                # pylint: disable=invalid-name
        """Create special context for lambda"""
        self.max_line(node)
        self.special.enable()
        self.visit(node.args)
        self.special.disable()
        self.visit(node.body)
        self.special.pop()

    def _visit_ListComp(self, node):                                             # pylint: disable=invalid-name
        """Create special context for ListComp"""
        self.max_line(node)
        #self.add(node.uid, "fn", node.lineno)
        self.special.enable()
        self.special.disable()
        for gen in node.generators:
            self.visit(gen)
        self.visit(node.elt)
        self.special.pop()

    def visit_ListComp(self, node):                                              # pylint: disable=invalid-name
        """Visit LiComp"""
        self.new_comprehension(node)

    if sys.version_info < (3, 0):
        visit_ListComp = _visit_ListComp                                         # pylint: disable=invalid-name

    def visit_SetComp(self, node):                                               # pylint: disable=invalid-name
        """Visit SetComp"""
        self.new_comprehension(node)

    def visit_GeneratorExp(self, node):                                          # pylint: disable=invalid-name
        """Visit GeneratorExp"""
        self.new_comprehension(node)

    def visit_DictComp(self, node):                                              # pylint: disable=invalid-name
        """Create special context for DictComp"""
        self.new_comprehension(node)

    def visit_comprehension(self, node):
        """Create special context for comprehension"""
        self.max_line(node)
        self.special.use = True
        self.visit(node.target)
        self.special.disable()
        self.visit(node.iter)
        for _if in node.ifs:
            self.visit(_if)

    def visit_Call(self, node):                                                  # pylint: disable=invalid-name
        """Create special dependency for calls"""
        self.max_line(node)
        self.add(variable(node.uid, "call"), "fn", node.lineno)

    def visit_Print(self, node):                                                 # pylint: disable=invalid-name
        """Create special dependency for calls"""
        self.max_line(node)
        self.add(variable(node.uid, "print"), "fn print", node.lineno)

    def visit_Import(self, node):                                                # pylint: disable=invalid-name
        """Create special dependency for imports"""
        self.max_line(node)
        self.add(variable(node.uid, "import"), "import", node.lineno)

    def visit_ImportFrom(self, node):                                            # pylint: disable=invalid-name
        """Create special dependency for imports"""
        self.max_line(node)
        self.add(variable(node.uid, "import from"), "import from", node.lineno)


class ComprehensionVisitor(AssignRightVisitor):
    """Dependency of variables in comprehension"""

    def visit_ListComp(self, node):
        """Visit ListComp"""
        self._visit_ListComp(node)

    def visit_SetComp(self, node):                                               # pylint: disable=invalid-name
        """Visit SetComp"""
        self._visit_ListComp(node)

    def visit_GeneratorExp(self, node):                                          # pylint: disable=invalid-name
        """Visit GeneratorExp"""
        self._visit_ListComp(node)

    def visit_DictComp(self, node):                                              # pylint: disable=invalid-name
        """Create special context for DictComp"""
        self.max_line(node)
        self.special.enable()
        self.special.disable()
        for gen in node.generators:
            self.visit(gen)
        self.visit(node.key)
        self.visit(node.value)
        self.special.pop()

    def visit_Call(self, node):                                                  # pylint: disable=invalid-name
        """Create special dependency for calls"""
        self.max_line(node)
        self.generic_visit(node)


def tuple_or_list(node):
    """Check if node is tuple or list"""
    return isinstance(node, ast.Tuple) or isinstance(node, ast.List)


def assign_dependencies(target, value, dependencies, typ,                        # pylint: disable=too-many-arguments
                        dep_typ="direct", aug=False, testlist_star_expr=True):
    """Add dependencies to <dependencies>
    <target> depends on <value>
    <target> may also depends on loop if <aug>
                                           or if there is a self_reference
    Expand assign dependencies if <testlist_star_expr>
    """

    left, right = AssignLeftVisitor(), AssignRightVisitor()

    if testlist_star_expr and tuple_or_list(target) and tuple_or_list(value):
        for i, targ in enumerate(target.elts):
            assign_dependencies(targ, value.elts[i], dependencies,
                                typ, dep_typ=dep_typ, testlist_star_expr=True)
        return

    left.visit(target)
    if value:
        right.visit(value)

    for name, _, lineno in left.names:
        var = variable(name, typ)
        dependencies[lineno][var]
        lineno = right.line if right.line != -1 else lineno
        self_reference = False
        for value, _, _ in right.names:
            dependencies[lineno][var].append(Dependency(value, dep_typ))
            if name == value:
                self_reference = True

        if aug:
            dependencies[lineno][var].append(Dependency(name, dep_typ))
            self_reference = True

        if self_reference:
            dependencies[lineno][var].append(Dependency("<self>", "loop"))


def assign_artificial_dependencies(target, artificial, dependencies, typ):
    """Add artificial dependencies to <dependencies>
    <target> depends on <artificial>
    """
    left = AssignLeftVisitor()

    left.visit(target)

    for name, _, _ in left.names:
        var = variable(name, typ)
        lineno = target.lineno
        dependencies[lineno][var].append(Dependency(artificial, "direct"))


def assign_right(lineno, target, value, dependencies):
    """Add dependencies to <dependencies>
    <target> depends on <value>
    """

    right = AssignRightVisitor()
    if value:
        right.visit(value)

    dependencies[lineno][target]
    for name, _, _ in right.names:
        dependencies[lineno][target].append(Dependency(name, "direct"))

class SlicingVisitor(FunctionVisitor):                                           # pylint: disable=too-many-instance-attributes, too-many-public-methods
    """Visitor that captures required information for program slicing"""

    def __init__(self, *args):
        super(SlicingVisitor, self).__init__(*args)
        self.line_usages = defaultdict(lambda: {
            "Load": [], "Store": [], "Del": [],
            "AugLoad": [], "AugStore": [], "Param": [],
        })
        self.dependencies = defaultdict(lambda: defaultdict(list))

        self.gen_dependencies = defaultdict(lambda: defaultdict(list))
        self.call_by_col = defaultdict(dict)
        self.function_calls_by_lasti = defaultdict(dict)
        self.with_enter_by_lasti = defaultdict(dict)
        self.with_exit_by_lasti = defaultdict(dict)
        self.function_calls_list = []
        self.with_list = []
        self.imports_list = []
        self.imports = set()
        self.iters_list = []
        self.iters = defaultdict(set)

        self.condition_stack = []
        self.conditions = {}
        self.loops = {}
        self.disasm = []

        # Python 2
        self.print_item_list = []
        self.print_newline_list = []

    def add_call_function(self, node, cls, *args, **kwargs):
        """Add special CallFunction of class <cls> to list
        Visit <node> to create dependencies
        Optional args: <call_list> is the list that will get the call
        """
        call_list = self.function_calls_list
        if "call_list" in kwargs and kwargs["call_list"] is not None:
            call_list = kwargs["call_list"]
        function_call = cls(AssignRightVisitor, *args)
        function_call.name = self.extract_code(node)
        function_call.visit(node)
        function_call.line, function_call.col = node.uid
        call_list.append(function_call)
        return function_call

    def add_decorators(self, node, original_name):
        """Add special function calls for decorators"""
        decorators = [self.add_decorator(dec_node)
                      for dec_node in node.decorator_list]
        lineno = node.lineno
        name = variable(original_name, 'call')
        for dec in reversed(decorators):
            uid = (dec.line, dec.col)
            self.dependencies[lineno][name].append(Dependency(uid, "direct"))
            #dec.args.append([name])
            name = variable(uid, 'call')

    def add_decorator(self, node):
        """Add special function call for decorator"""
        dec_node = ast.Call()
        dec_node.func = node
        dec_node.args = []
        dec_node.keywords = []
        if sys.version_info < (3, 5):
            dec_node.starargs = None
            dec_node.kwargs = None
        dec_node.first_col = node.first_col
        dec_node.first_line = node.first_line
        dec_node.last_col, dec_node.last_line = node.last_col, node.last_line
        dec_node.uid = (dec_node.first_line, dec_node.first_col)
        dec = self.add_call_function(dec_node, Decorator)
        self.call_by_col[dec.line][dec.col] = dec
        self.add_func_dependency(dec)
        return dec

    def add_new_comprehension(self, typ, node, add_call=True):
        """Create comprehension call and generators"""
        if add_call:
            call = self.add_call_function(node, GeneratorCall, typ)
            self.call_by_col[call.line][call.col] = call
            right = ComprehensionVisitor()
            right.visit(node)
            line, uid = call.line, variable((call.line, call.col), "return")
            for name, _, _ in right.names:
                self.dependencies[line][uid].append(Dependency(name, "direct"))
        for gen_node in node.generators:
            self.add_generator(typ, gen_node)

    def add_generator(self, typ, node):
        """Add special function call for generator"""
        self.add_call_function(node, Generator, typ, call_list=self.iters_list)

        assign_dependencies(node.target, node.iter, self.gen_dependencies,
                            "normal", testlist_star_expr=False)
        for nif in node.ifs:
            self.visit(nif)
            assign_dependencies(node.target, nif, self.gen_dependencies,
                                "conditional", testlist_star_expr=False)

    def add_with(self, node):
        """Cross version visit With and create dependencies"""
        _with = self.add_call_function(node, With, call_list=self.with_list)
        _with.line, _with.col = node.context_expr.uid
        if node.optional_vars:
            assign_artificial_dependencies(node.optional_vars,
                                           node.context_expr.uid,
                                           self.dependencies,
                                           "normal")
        self.call_by_col[_with.line][_with.col] = _with

    def add_return_yield(self, node, label):
        """Create special <label> variable
        Use for return and yield dependencies
        """
        self.new_var(ast.Name(label, ast.Store(), lineno=node.lineno),
                     "virtual", dep_typ="return", value=node.value)

    def new_var(self, name, typ, dep_typ="direct", value=None, **kwargs):
        """Create new variable"""
        assign_dependencies(name, value, self.dependencies, typ,
                            dep_typ=dep_typ,
                            testlist_star_expr=False, **kwargs)

    def add_func_dependency(self, call):
        """Create dependency for call nodes that accept expr as func"""
        for name in call.func:
            uid = variable((call.line, call.col), "call")
            self.dependencies[call.line][uid].append(
                Dependency(name, "direct"))

    def visit_stmts(self, stmts):
        """Visit stmts"""
        for stmt in stmts:
            self.visit(stmt)

    def visit_AugAssign(self, node):                                             # pylint: disable=invalid-name
        """Visit AugAssign. Create dependencies"""
        self.new_var(node.target, "normal", value=node.value, aug=True)
        self.generic_visit(node)

    def visit_Assign(self, node):                                                # pylint: disable=invalid-name
        """Visit Assign. Create dependencies"""
        for target in node.targets:
            assign_dependencies(target, node.value, self.dependencies,
                                "normal")
        self.generic_visit(node)

    def visit_For(self, node):                                                   # pylint: disable=invalid-name
        """Visit For. Create dependencies"""
        loop = Loop(node, "for")
        self.loops[loop.first_line] = loop
        _iter = self.add_call_function(node.iter, ForIter,
                                       call_list=self.iters_list)
        _iter.col += 1
        self.call_by_col[_iter.line][_iter.col] = _iter
        loop.maybe_call = (_iter.line, _iter.col)
        loop.add_iterable(node.iter, AssignRightVisitor)
        loop.add_iter_var(node.target, AssignLeftVisitor)
        loop.first_line_in_scope = node.body[0].first_line

        self.visit(node.target)
        self.visit(node.iter)
        self.visit_stmts(node.body)
        self.visit_stmts(node.orelse)

    def visit_AsyncFor(self, node):                                              # pylint: disable=invalid-name
        """Visit For. Create dependencies. Python 3.5"""
        self.visit_For(node)

    def visit_While(self, node):                                                 # pylint: disable=invalid-name
        """Visit While. Create conditional dependencies"""
        loop = Loop(node, "while")
        self.loops[loop.first_line] = loop
        self.visit_If(node)

    def visit_If(self, node):                                                    # pylint: disable=invalid-name
        """Visit If. Create conditional dependencies"""
        condition = Condition(node)
        self.conditions[condition.first_line] = condition
        condition.add_test(node.test, AssignRightVisitor)
        self.visit(node.test)
        self.condition_stack.append(condition)
        self.visit_stmts(node.body)
        self.visit_stmts(node.orelse)
        self.condition_stack.pop()

    def visit_Name(self, node):                                                  # pylint: disable=invalid-name
        """Visit Name. Crate Usage"""
        self.line_usages[node.lineno][type(node.ctx).__name__].append(node.id)
        super(SlicingVisitor, self).visit_Name(node)

    def visit_Call(self, node):                                                  # pylint: disable=invalid-name
        """Visit Call. Create special function call"""
        super(SlicingVisitor, self).visit_Call(node)
        call = self.add_call_function(node, FunctionCall)
        self.add_func_dependency(call)
        self.call_by_col[call.line][call.col] = call

    def visit_Print(self, node):                                                 # pylint: disable=invalid-name
        """Visit Print node. Create special function call
        Python 2 Only
        """
        self.generic_visit(node)
        _print = self.add_call_function(node, Print,
                                        call_list=self.print_newline_list)
        for _ in node.values:
            self.print_item_list.append(_print)
        self.call_by_col[_print.line][_print.col] = _print

    def visit_Return(self, node):                                                # pylint: disable=invalid-name
        """Visit Return. Create special variable"""
        for condition in self.condition_stack:
            condition.has_return = True
        self.add_return_yield(node, "return")
        if node.value:
            self.visit(node.value)

    def visit_Yield(self, node):                                                 # pylint: disable=invalid-name
        """Visit Yield. Create special variable"""
        self.add_return_yield(node, "yield")
        if node.value:
            self.visit(node.value)

    def visit_Import(self, node):                                                # pylint: disable=invalid-name
        """Visit Import"""
        self.generic_visit(node)

        for alias in node.names:
            _import = self.add_call_function(node, Import,
                                             call_list=self.imports_list)
            self.call_by_col[_import.line][_import.col] = _import

            name = ast.Name(alias.asname if alias.asname else alias.name,
                            ast.Store(), lineno=node.lineno)
            self.new_var(name, "import", value=node)

    def visit_ImportFrom(self, node):                                            # pylint: disable=invalid-name
        """Visit ImportFrom"""
        self.generic_visit(node)

        _import = self.add_call_function(node, Import,
                                         call_list=self.imports_list)
        self.call_by_col[_import.line][_import.col] = _import

        for alias in node.names:
            name = ast.Name(alias.asname if alias.asname else alias.name,
                            ast.Store(), lineno=node.lineno)
            self.new_var(name, "import from", value=node)

    def visit_ListComp(self, node):                                              # pylint: disable=invalid-name
        """Visit ListComp. Create special function call on Python 3"""
        self.add_new_comprehension("List", node, sys.version_info >= (3, 0))
        self.generic_visit(node)

    def visit_SetComp(self, node):                                               # pylint: disable=invalid-name
        """Visit SetComp. Create special function call"""
        self.add_new_comprehension("Set", node)
        self.generic_visit(node)

    def visit_DictComp(self, node):                                              # pylint: disable=invalid-name
        """Visit DictComp. Create special function call"""
        self.add_new_comprehension("Dict", node)
        self.generic_visit(node)

    def visit_GeneratorExp(self, node):                                          # pylint: disable=invalid-name
        """Visit GeneratorExp. Create special function call"""
        self.add_new_comprehension("Generator", node)
        self.generic_visit(node)

    def visit_ClassDef(self, node):                                              # pylint: disable=invalid-name
        """Visit ClassDef. Create special function call"""
        name = ast.Name(node.name, ast.Store(), lineno=node.lineno)
        name.first_line, name.first_col = name.uid = node.uid
        name.first_col += 1
        name.last_line = name.first_line
        name.last_col = name.first_col + len(node.name)
        _class = self.add_call_function(name, ClassDef)
        self.call_by_col[_class.line][_class.col] = _class

        line = node.lineno
        uid = (_class.line, _class.col)
        if not node.bases:
            assign_right(line, variable(uid, "call"), None, self.dependencies)


        for base in node.bases:
            assign_right(line, variable(uid, "call"), base, self.dependencies)


        self.add_decorators(node, uid)
        super(SlicingVisitor, self).visit_ClassDef(node)

    def visit_FunctionDef(self, node):                                           # pylint: disable=invalid-name
        """Visit FunctionDef"""
        name = ast.Name(node.name, ast.Store(), lineno=node.lineno)
        self.new_var(name, "function definition", value=None)

        self.add_decorators(node, node.name)
        super(SlicingVisitor, self).visit_FunctionDef(node)

    def visit_AsyncFunctionDef(self, node):                                      # pylint: disable=invalid-name
        """Visit AsyncFunctionDef. Python 3.5"""
        name = ast.Name(node.name, ast.Store(), lineno=node.lineno)
        self.new_var(name, "function definition", value=None)

        self.add_decorators(node, node.name)
        super(SlicingVisitor, self).visit_AsyncFunctionDef(node)

    def visit_Assert(self, node):                                                # pylint: disable=invalid-name
        """Visit Assert. Create special function call"""
        self.generic_visit(node)
        if node.msg:
            self.add_call_function(node, Assert, node.msg)

        # ToDo: with msg self.function_calls_list.append(cls)

    def visit_With(self, node):                                                  # pylint: disable=invalid-name
        """Visit With. Create special With enter/exit on Python 2"""
        self.generic_visit(node)
        if sys.version_info < (3, 0):
            self.add_with(node)

    def visit_withitem(self, node):
        """Visit Assert. Create special With enter/exit on Python 3"""
        self.generic_visit(node)
        self.add_with(node)

    def teardown(self):
        """Matches AST call order to call order in disassembly
        Possible issues:
        1- The disassembly may be specific to cpython. It may not work on other
        implementations
        2- If the order in AST is not correct, the matching will fail
        3- If there are other CALL_FUNCTION that are not considered in the AST
        the matching will fail
            both visit_ClassDef and visit_Call generates CALL_FUNCTION
        4- If some function is called without an explict CALL_FUNCTION
            __enter__: SETUP_WITH
            __exit__: WITH_CLEANUP
        """
        self.with_list.sort(key=lambda x: (x.line, x.col))
        end_with = {}
        operations = [
            AddCall(CALL_FUNCTIONS,
                    self.function_calls_list, self.function_calls_by_lasti),
            AddCall(PRINT_ITEMS,
                    self.print_item_list, self.function_calls_by_lasti),
            AddCall(PRINT_NEW_LINES,
                    self.print_newline_list, self.function_calls_by_lasti),
            AddImport(IMPORT_NAMES, self.imports,
                      self.imports_list, self.function_calls_by_lasti),
            AddWith(SETUP_WITH | SETUP_ASYNC_WITH, self.with_enter_by_lasti,
                    end_with, self.with_list, self.function_calls_by_lasti),
            AddWithCleanup(WITH_CLEANUP, self.with_exit_by_lasti,
                           end_with, self.function_calls_by_lasti),
            AddForIter(FOR_ITERS, self.iters,
                       self.iters_list, self.function_calls_by_lasti),
            AddGetIter(GET_ITERS, self.iters,
                       self.iters_list, self.function_calls_by_lasti),
        ]
        for inst in self.disasm:
            for operation in operations:
                operation.process(inst)


class AddCall(object):                                                           # pylint: disable=too-few-public-methods
    """Enrich disasm with calls and other instructions that cause calls"""

    def __init__(self, opcodes, clist, by_lasti):
        self.opcodes = opcodes
        self.clist = clist
        self.by_lasti = by_lasti
        self.index = 0

    def process(self, inst):
        """Process disasm instruction"""
        if inst.opcode in self.opcodes:
            call = safeget(self.clist, self.index)
            call.lasti = inst.offset
            self.by_lasti[inst.line][inst.offset] = call
            self.index += 1
            inst.extra = call
            return call


class AddImport(AddCall):                                                        # pylint: disable=too-few-public-methods
    """Enrich disasm with Imports"""

    def __init__(self, opcodes, imports, *args, **kwargs):
        super(AddImport, self).__init__(opcodes, *args, **kwargs)
        self.imports = imports

    def process(self, inst):
        """Process disasm instruction"""
        _import = super(AddImport, self).process(inst)
        if _import:
            self.imports.add(inst.line)


class AddWith(AddCall):                                                          # pylint: disable=too-few-public-methods
    """Enrich disasm with With statements"""

    def __init__(self, opcodes, with_enter_lasti, end_with, *args, **kwargs):
        super(AddWith, self).__init__(opcodes, *args, **kwargs)
        self.with_enter_by_lasti = with_enter_lasti
        self.end_with = end_with

    def process(self, inst):
        """Process disasm instruction"""
        _with = super(AddWith, self).process(inst)
        if _with:
            self.with_enter_by_lasti[inst.line][inst.offset] = _with
            end = int(inst.argrepr[3:])
            _with.end = end
            self.end_with[end] = _with
            return _with


class AddWithCleanup(namedtuple(
        "WithCleanup", "opcodes with_exit_by_lasti end_with by_lasti")):
    """Enrich disasm with With cleanups"""
    def process(self, inst):
        """Process disasm instruction"""
        if inst.opcode in self.opcodes:
            _with = self.end_with[inst.offset]
            del self.end_with[inst.offset]
            _with.end_line = inst.line
            self.by_lasti[inst.line][inst.offset] = _with
            self.with_exit_by_lasti[inst.line][inst.offset] = _with
            inst.extra = _with
            return _with


class AddForIter(AddCall):                                                        # pylint: disable=too-few-public-methods
    """Enrich disasm with ForIters"""

    def __init__(self, opcodes, iters, *args, **kwargs):
        super(AddForIter, self).__init__(opcodes, *args, **kwargs)
        self.iters = iters

    def process(self, inst):
        """Process disasm instruction"""
        _for = super(AddForIter, self).process(inst)
        if _for:
            self.iters[inst.line].add(inst.offset)


class AddGetIter(AddForIter):                                                     # pylint: disable=too-few-public-methods
    """Enrich disasm with GetIters"""

    def process(self, inst):
        """Process disasm instruction"""
        if sys.version_info < (3, 0):
            super(AddGetIter, self).process(inst)
        else:
            if inst.opcode in self.opcodes:
                self.iters[inst.line].add(inst.offset)
