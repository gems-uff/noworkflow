# Copyright (c) 2016 Universidade Federal Fluminense (UFF)
# Copyright (c) 2016 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""Define executable bytecode interpreter"""
from __future__ import (absolute_import, print_function,
                        division, unicode_literals)

import sys
import types
import dis

from dis import opmap

from collections import OrderedDict
from opcode import cmp_op

from .interpreter import Interpreter


CALL_FUNCTION = opmap["CALL_FUNCTION"]
CALL_FLAG_VAR = 1
CALL_FLAG_KW = 2


COMPARE = {
    cmp_op.index("<"): (lambda a, b: a < b),
    cmp_op.index("<="): (lambda a, b: a <= b),
    cmp_op.index("=="): (lambda a, b: a == b),
    cmp_op.index("!="): (lambda a, b: a != b),
    cmp_op.index(">"): (lambda a, b: a > b),
    cmp_op.index(">="): (lambda a, b: a >= b),
    cmp_op.index("in"): (lambda a, b: a in b),
    cmp_op.index("not in"): (lambda a, b: a not in b),
    cmp_op.index("is"): (lambda a, b: a is b),
    cmp_op.index("is not"): (lambda a, b: a is not b),
    cmp_op.index("exception match"): (lambda a, b: a == b),
    cmp_op.index("BAD"): (lambda a, b: False)
}


class CodeInterpreter(Interpreter):
    """Code Interpreter.
    Replace constructor to get code, locals and globals
    """

    def __init__(self, code, f_locals, f_globals, line_offset=0):
        super(CodeInterpreter, self).__init__(
            code.co_code, varnames=code.co_varnames, names=code.co_names,
            constants=code.co_consts,
            cells=code.co_cellvars + code.co_freevars,
            linestarts=OrderedDict(dis.findlinestarts(code)),
            line_offset=line_offset)

        self._code = code
        self._locals = f_locals
        self._globals = f_globals

        self.stack = []
        self.result = None

    def execute(self):
        """Iterate through interpreter"""
        for _ in self:
            pass

    def _pop_last_n(self, number):
        """Pop last n objects from stack"""
        return reversed([self.stack.pop() for _ in range(number)])


class ExecInterpreter(CodeInterpreter):                                          # pylint: disable=too-many-public-methods
    """Bytecode interpreter that executes it
    Currently, it is working only for Expressions
    """

    def __init__(self, code, f_locals, f_globals, line_offset=0):
        if not hasattr(self, "_known_missing"):
            self._known_missing = set()
        self._known_missing |= {
            "BREAK_LOOP", "CONTINUE_LOOP", "RETURN_VALUE", "YIELD_VALUE",
            "IMPORT_STAR", "POP_BLOCK", "POP_EXCEPT", "END_FINALLY",
            "SETUP_WITH", "WITH_CLEANUP_START", "WITH_CLEANUP_FINISH",
            "WITH_CLEANUP", "IMPORT_NAME", "IMPORT_FROM", "SETUP_LOOP",
            "SETUP_EXCEPT", "SETUP_FINALLY", "LOAD_CLOSURE", "LOAD_DEREF",
            "LOAD_CLASSDEREF", "STORE_DEREF", "DELETE_DEREF", "RAISE_VARARGS",
            "MAKE_CLOSURE", "UNPACK_SEQUENCE"
        }
        super(ExecInterpreter, self).__init__(
            code, f_locals, f_globals, line_offset=0)

    def _call(self, nargs, flags=0, nkw=0):
        """Execute call"""
        var, kwargs = [], {}
        if flags & CALL_FLAG_KW:
            kwargs = self.stack.pop()
        if flags & CALL_FLAG_VAR:
            var = self.stack.pop()
        for _ in range(nkw):
            value = self.stack.pop()
            key = self.stack.pop()
            kwargs[key] = value
        args = list(self._pop_last_n(nargs))
        func = self.stack[-1]
        self.stack[-1] = func(*(args + var), **kwargs)

    def _binary(self, func):
        """Execute binary operation"""
        tos = self.stack.pop()
        self.stack[-1] = func(self.stack[-1], tos)

    def _inplace(self, func):
        """Execute inplace operation"""
        tos = self.stack.pop()
        self.stack[-1] = func(self.stack[-1], tos)

    def _unary(self, func):
        """Execute unary operation"""
        self.stack[-1] = func(self.stack[-1])

    def extended_arg(self):
        """EXTENDED_ARG opcode"""
        self._extended_arg = self.oparg * 65536

    def load_fast(self):
        """LOAD_FAST opcode"""
        self.stack.append(self._locals[self.varnames[self.oparg]])

    def load_global(self):
        """LOAD_GLOBAL opcode"""
        self.stack.append(self._globals[self.names[self.oparg]])

    def load_attr(self):
        """LOAD_ATTR opcode"""
        self.stack[-1] = getattr(self.stack[-1], self.names[self.oparg])

    def load_const(self):
        """LOAD_CONST opcode"""
        self.stack.append(self.consts[self.oparg])

    def load_name(self):
        """LOAD_NAME opcode"""
        self.stack.append(self.names[self.oparg])

    def build_tuple(self):
        """BUILD_TUPLE opcode"""
        self.stack.append(tuple(self._pop_last_n(self.oparg)))

    def build_list(self):
        """BUILD_LIST opcode"""
        self.stack.append(list(self._pop_last_n(self.oparg)))

    def build_map(self):
        """BUILD_MAP opcode"""
        self.stack.append({})

    def build_set(self):
        """BUILD_SET opcode"""
        self.stack.append(set(self._pop_last_n(self.oparg)))

    def store_map(self):
        """STORE_MAP opcode"""
        key, value = self.stack.pop(), self.stack.pop()
        self.stack[-1][key] = value

    def call_function(self):
        """CALL_FUNCTION opcode"""
        self._call(self.oparg & 0xff, flags=(self.opcode - CALL_FUNCTION) & 3,
                   nkw=(self.oparg >> 8) & 0xff)

    def call_function_var(self):
        """CALL_FUNCTION_VAR opcode"""
        self.call_function()

    def call_function_kw(self):
        """CALL_FUNCTION_KW opcode"""
        self.call_function()

    def call_function_var_kw(self):
        """CALL_FUNCTION_VAR_KW opcode"""
        self.call_function()

    def make_function(self):
        """MAKE_FUNCTION opcode. Python 3 version"""
        qualname = self.stack.pop()
        func = types.FunctionType(self.stack.pop(), self._globals, qualname)
        posdefaults = self.oparg & 0xff
        kwdefaults = (self.oparg >> 8) & 0xff
        num_annotations = (self.oparg >> 16) & 0x7fff

        if num_annotations:
            _names = self.stack.pop()
            _values = self._pop_last_n(num_annotations - 1)
            func.__annotations__ = dict(zip(_names, _values))

        if kwdefaults:
            defaults = {}
            for _ in range(kwdefaults):
                _value = self.stack.pop()
                _key = self.stack.pop()
                defaults[_key] = _value
            func.__kwdefaults__ = defaults

        tup = tuple(self._pop_last_n(posdefaults))
        func.__defaults__ = tup

        self.stack.append(func)

    def build_slice(self):
        """BUILD SLICE opcode"""
        self.stack.append(slice(*self._pop_last_n(self.oparg)))

    def binary_add(self, func=lambda a, b: a + b):
        """BINARY_ADD opcode"""
        self._binary(func)

    def binary_and(self, func=lambda a, b: a & b):
        """BINARY_AND opcode"""
        self._binary(func)

    def binary_floor_divide(self, func=lambda a, b: a // b):
        """BINARY_FLOOR_DIVIDE opcode"""
        self._binary(func)

    def binary_lshift(self, func=lambda a, b: a << b):
        """BINARY_LSHIFT opcode"""
        self._binary(func)

    def binary_modulo(self, func=lambda a, b: a % b):
        """BINARY_MODULO opcode"""
        self._binary(func)

    def binary_multiply(self, func=lambda a, b: a * b):
        """BINARY_MULTIPLY opcode"""
        self._binary(func)

    def binary_or(self, func=lambda a, b: a | b):
        """BINARY_OR opcode"""
        self._binary(func)

    def binary_power(self, func=lambda a, b: a ** b):
        """BINARY_POWER opcode"""
        self._binary(func)

    def binary_rshift(self, func=lambda a, b: a >> b):
        """BINARY_RSHIFT opcode"""
        self._binary(func)

    def binary_subscr(self, func=lambda a, b: a[b]):
        """BINARY_SUBSCR opcode"""
        self._binary(func)

    def binary_subtract(self, func=lambda a, b: a - b):
        """BINARY_SUBTRACT opcode"""
        self._binary(func)

    def binary_true_divide(self, func=lambda a, b: a / b):
        """BINARY_TRUE_DIVIDE opcode"""
        self._binary(func)

    def binary_xor(self, func=lambda a, b: a ^ b):
        """BINARY_XOR opcode"""
        self._binary(func)

    def inplace_add(self, func=lambda a, b: a + b):
        """INPLACE_ADD opcode"""
        self._inplace(func)

    def inplace_and(self, func=lambda a, b: a & b):
        """INPLACE_AND opcode"""
        self._inplace(func)

    def inplace_floor_divide(self, func=lambda a, b: a // b):
        """INPLACE_FLOOR_DIVIDE opcode"""
        self._inplace(func)

    def inplace_lshift(self, func=lambda a, b: a << b):
        """INPLACE_LSHIFT opcode"""
        self._inplace(func)

    def inplace_modulo(self, func=lambda a, b: a % b):
        """INPLACE_MODULO opcode"""
        self._inplace(func)

    def inplace_multiply(self, func=lambda a, b: a * b):
        """INPLACE_MULTIPLY opcode"""
        self._inplace(func)

    def inplace_or(self, func=lambda a, b: a | b):
        """INPLACE_OR opcode"""
        self._inplace(func)

    def inplace_power(self, func=lambda a, b: a ** b):
        """INPLACE_POWER opcode"""
        self._inplace(func)

    def inplace_rshift(self, func=lambda a, b: a >> b):
        """INPLACE_RSHIFT opcode"""
        self._inplace(func)

    def inplace_subtract(self, func=lambda a, b: a - b):
        """INPLACE_SUBTRACT opcode"""
        self._inplace(func)

    def inplace_true_divide(self, func=lambda a, b: a / b):
        """INPLACE_TRUE_DIVIDE opcode"""
        self._inplace(func)

    def inplace_xor(self, func=lambda a, b: a ^ b):
        """INPLACE_XOR opcode"""
        self._inplace(func)

    def unary_invert(self, func=lambda a: ~a):
        """UNARY_INVERT opcode"""
        self._unary(func)

    def unary_negative(self, func=lambda a: -a):
        """UNARY_NEGATIVE opcode"""
        self._unary(func)

    def unary_not(self, func=lambda a: not a):
        """UNARY_NOT opcode"""
        self._unary(func)

    def unary_positive(self, func=lambda a: +a):
        """UNARY_POSITIVE opcode"""
        self._unary(func)

    def rot_two(self):
        """ROT_TWO opcode"""
        sta = self.stack
        sta[-1], sta[-2] = sta[-2], sta[-1]

    def rot_three(self):
        """ROT_THREE opcode"""
        sta = self.stack
        sta[-1], sta[-2], sta[-3] = sta[-2], sta[-3], sta[-1]

    def dup_top(self):
        """DUP_TOP opcode"""
        self.stack.append(self.stack[-1])

    def pop_top(self):
        """POP_TOP opcode"""
        self.stack.pop()

    def compare_op(self):
        """COMPARE_OP opcode"""
        tos, tos1 = self.stack.pop(), self.stack.pop()
        self.stack.append(COMPARE[self.oparg](tos1, tos))

    def jump_if_false_or_pop(self):
        """JUMP_IF_FALSE_OR_POP opcode"""
        tos = self.stack.pop()
        if not tos:
            self.lasti = self.oparg
            self.stack.append(tos)

    def jump_if_true_or_pop(self):
        """JUMP_IF_TRUE_OR_POP opcode"""
        tos = self.stack.pop()
        if tos:
            self.lasti = self.oparg
            self.stack.append(tos)

    def jump_forward(self):
        """JUMP_FORWARD opcode"""
        self.lasti += self.oparg

    def pop_jump_if_true(self):
        """POP_JUMP_IF_TRUE opcode"""
        if self.stack.pop():
            self.lasti = self.oparg

    def pop_jump_if_false(self):
        """POP_JUMP_IF_FALSE opcode"""
        if not self.stack.pop():
            self.lasti = self.oparg

    def jump_absolute(self):
        """JUMP_ABSOLUTE opcode"""
        self.lasti = self.oparg

    def get_iter(self):
        """GET_ITER opcode"""
        self.stack[-1] = iter(self.stack[-1])

    def list_append(self):
        """LIST_APPEND opcode"""
        tos = self.stack.pop()
        self.stack[-self.oparg].append(tos)

    def set_add(self):
        """SET_ADD opcode"""
        tos = self.stack.pop()
        self.stack[-self.oparg].add(tos)

    def map_add(self):
        """MAP_ADD opcode"""
        tos, tos1 = self.stack.pop(), self.stack.pop()
        self.stack[-self.oparg][tos] = tos1

    def for_iter(self):
        """FOR_ITER opcode"""
        try:
            self.stack.append(next(self.stack[-1]))
        except StopIteration:
            self.stack.pop()
            self.lasti += self.oparg

    def store_fast(self):
        """STORE_FAST opcode"""
        self._locals[self.varnames[self.oparg]] = self.stack.pop()

    def store_subscr(self):
        """STORE_SUBSCR opcode"""
        key, var, value = self.stack.pop(), self.stack.pop(), self.stack.pop()
        var[key] = value

    def store_name(self):
        """STORE_NAME opcode"""
        self._locals[self.names[self.oparg]] = self.stack.pop()

    def store_attr(self):
        """STORE_ATTR opcode"""
        var, value = self.stack.pop(), self.stack.pop()
        setattr(var, self.names[self.oparg], value)

    def store_global(self):
        """STORE_GLOBAL opcode"""
        self._globals[self.names[self.oparg]] = self.stack.pop()

    def delete_fast(self):
        """DELETE_FAST opcode"""
        del self._locals[self.varnames[self.oparg]]

    def delete_subscr(self):
        """DELETE_SUBSCR opcode"""
        key, var = self.stack.pop(), self.stack.pop()
        del var[key]

    def delete_name(self):
        """DELETE_NAME opcode"""
        del self._locals[self.names[self.oparg]]

    def delete_attr(self):
        """DELETE_ATTR opcode"""
        var = self.stack.pop()
        delattr(var, self.names[self.oparg])

    def delete_global(self):
        """DELETE_GLOBAL opcode"""
        del self._globals[self.names[self.oparg]]

    def print_expr(self):
        """PRINT_EXPR opcode"""
        self.result = self.stack.pop()


class Py2Codes(ExecInterpreter):
    """Bytecodes specific for Python 2"""

    def __init__(self, *args, **kwargs):
        if not hasattr(self, "_known_missing"):
            self._known_missing = set()
        self._known_missing |= {
            "BUILD_CLASS", "EXEC_STMT", "LOAD_LOCALS", "PRINT_ITEM",
            "PRINT_ITEM_TO", "PRINT_NEWLINE", "PRINT_NEWLINE_TO", "STOP_CODE"
        }
        super(Py2Codes, self).__init__(*args, **kwargs)

    def make_function(self):
        """MAKE_FUNCTION opcode"""
        tup = tuple(self._pop_last_n(self.oparg))
        func = types.FunctionType(self.stack.pop(), self._globals)
        func.func_defaults = tup
        self.stack.append(func)

    def binary_divide(self):
        """BINARY_DIVIDE opcode"""
        self._binary(lambda a, b: a / b)

    def binary_true_divide(self, func=lambda a, b: (
            float(a) if isinstance(a, int) else a) / b):
        """BINARY_TRUE_DIVIDE opcode"""
        self._binary(func)

    def inplace_divide(self):
        """INPLACE_DIVIDE opcode"""
        self._inplace(lambda a, b: a / b)

    def inplace_true_divide(self, func=lambda a, b: (
            float(a) if isinstance(a, int) else a) / b):
        """INPLACE_TRUE_DIVIDE opcode"""
        self._inplace(func)

    def unary_positive(self, func=repr):
        """UNARY_CONVERT opcode"""
        self._unary(func)

    def slice__0(self):
        """SLICE+0 opcode"""
        self.stack[-1] = self.stack[-1][:]

    def slice__1(self):
        """SLICE+1 opcode"""
        tos = self.stack.pop()
        self.stack[-1] = self.stack[-1][tos:]

    def slice__2(self):
        """SLICE+2 opcode"""
        tos = self.stack.pop()
        self.stack[-1] = self.stack[-1][:tos]

    def slice__3(self):
        """SLICE+3 opcode"""
        tos = self.stack.pop()
        tos1 = self.stack.pop()
        self.stack[-1] = self.stack[-1][tos1:tos]

    def rot_four(self):
        """ROT_FOUR opcode"""
        sta = self.stack
        sta[-1], sta[-2], sta[-3], sta[-4] = sta[-2], sta[-3], sta[-4], sta[-1]

    def dup_topx(self):
        """DUP_TOPX opcode"""
        topx = list(self._pop_last_n(self.oparg))
        self.stack = self.stack + topx + topx

    def store_slice__0(self):
        """STORE_SLICE+0 opcode"""
        var, value = self.stack.pop(), self.stack.pop()
        var[:] = value

    def store_slice__1(self):
        """STORE_SLICE+1 opcode"""
        sli, var, value = self.stack.pop(), self.stack.pop(), self.stack.pop()
        var[sli:] = value

    def store_slice__2(self):
        """STORE_SLICE+2 opcode"""
        sli, var, value = self.stack.pop(), self.stack.pop(), self.stack.pop()
        var[:sli] = value

    def store_slice__3(self):
        """STORE_SLICE+3 opcode"""
        sta = self.stack
        sli2, sli1, var, value = sta.pop(), sta.pop(), sta.pop(), sta.pop()
        var[sli1:sli2] = value

    def delete_slice__0(self):
        """DELETE_SLICE+0 opcode"""
        var = self.stack.pop()
        del var[:]

    def delete_slice__1(self):
        """STORE_SLICE+1 opcode"""
        sli, var = self.stack.pop(), self.stack.pop()
        del var[sli:]

    def delete_slice__2(self):
        """STORE_SLICE+2 opcode"""
        sli, var = self.stack.pop(), self.stack.pop()
        del var[:sli]

    def delete_slice__3(self):
        """STORE_SLICE+3 opcode"""
        sli2, sli1, var = self.stack.pop(), self.stack.pop(), self.stack.pop()
        del var[sli1:sli2]


class Py3Codes(ExecInterpreter):
    """Bytecodes specific for Python 3"""

    def __init__(self, *args, **kwargs):
        if not hasattr(self, "_known_missing"):
            self._known_missing = set()
        self._known_missing |= {
            "GET_YIELD_FROM_ITER", "BINARY_MATRIX_MULTIPLY", "GET_AWAITABLE",
            "GET_AITER", "GET_ANEXT", "BEFORE_ASYNC_WITH", "SETUP_ASYNC_WITH",
            "YIELD_FROM", "LOAD_BUILD_CLASS", "DELETE_DEREF",
            "LOAD_CLASSDEREF", "UNPACK_EX",
        }
        super(Py3Codes, self).__init__(*args, **kwargs)

    def dup_top_two(self):
        """DUP_TOP_TWO opcode"""
        top2 = list(self._pop_last_n(2))
        self.stack = self.stack + top2 + top2


PyInterpreter = (Py2Codes if sys.version_info >= (3, 0) else Py3Codes)           # pylint: disable=invalid-name
