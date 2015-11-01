# Copyright (c) 2015 Universidade Federal Fluminense (UFF)
# Copyright (c) 2015 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""Define bytecode functions"""
from __future__ import (absolute_import, print_function,
                        division, unicode_literals)

import dis
import sys
import types
import weakref
from bisect import bisect
from collections import defaultdict, OrderedDict
from dis import opmap
from opcode import HAVE_ARGUMENT, EXTENDED_ARG, cmp_op

from ..cross_version import PY3, cord, default_string, items, keys
from .io import redirect_output


def get_code_object(obj, compilation_mode="exec"):
    """ Return code object """
    if isinstance(obj, types.CodeType):
        return obj
    elif isinstance(obj, types.FrameType):
        return obj.f_code
    elif isinstance(obj, types.FunctionType):
        return obj.__code__
    elif isinstance(obj, str):
        try:
            return cross_compile(obj, "<string>", compilation_mode)
        except SyntaxError:
            raise ValueError("syntax error in passed string")
    else:
        raise TypeError("get_code_object() can not handle '%s' objects" %
                        (type(obj).__name__,))


def diss(obj, mode="exec", recurse=False):
    """ Disassemble code """
    _visit(obj, dis.dis, mode, recurse)

def ssc(obj, mode="exec", recurse=False):
    _visit(obj, dis.show_code, recurse)


def _visit(obj, visitor, mode="exec", recurse=False):
    """ Recursively disassemble """
    obj = get_code_object(obj, mode)
    visitor(obj)
    if recurse:
        for constant in obj.co_consts:
            if type(constant) is type(obj):
                _visit(constant, visitor, mode, recurse)


def get_dis(compiled, recurse=False):
    """ Return dis of compiled code """
    with redirect_output(['stdout']) as (stdout,):
        diss(compiled, recurse=recurse)
        return stdout.read_content().split('\n')


CALL_FUNCTION = opmap['CALL_FUNCTION']
CALL_FLAG_VAR = 1
CALL_FLAG_KW = 2


COMPARE = {
    cmp_op.index('<'): (lambda a, b: a < b),
    cmp_op.index('<='): (lambda a, b: a <= b),
    cmp_op.index('=='): (lambda a, b: a == b),
    cmp_op.index('!='): (lambda a, b: a != b),
    cmp_op.index('>'): (lambda a, b: a > b),
    cmp_op.index('>='): (lambda a, b: a >= b),
    cmp_op.index('in'): (lambda a, b: a in b),
    cmp_op.index('not in'): (lambda a, b: a not in b),
    cmp_op.index('is'): (lambda a, b: a is b),
    cmp_op.index('is not'): (lambda a, b: a is not b),
    cmp_op.index('exception match'): (lambda a, b: a == b),
    cmp_op.index('BAD'): (lambda a, b: False)
}


class Interpreter(object):

    def __init__(self, code, f_locals, f_globals, check_line=False):

        self._code = code
        self._locals = f_locals
        self._globals = f_globals
        self.check_line = check_line

        

        self.lasti = 0
        self.opi = 0
        self._extended_arg = 0

        self._co_code = code.co_code
        self.names = code.co_names
        self.varnames = code.co_varnames
        self.consts = code.co_consts
        self._size = len(self._co_code)
        self.stack = []


        self.opcode = None
        self.oparg = 0

        self._stop = False
        self._result = None

        self._map = {}
        self._extra = set()
        self._missing = set()
        self._supported = set()

        # TODO: Implement the following
        if not hasattr(self, '_known_missing'):
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
        self._create_map()


    def __iter__(self):
        """ Restart iterator """
        self._stop = False
        return self

    def __call__(self, lasti=0, extended_arg=0):
        self.lasti = lasti
        self._extended_arg = extended_arg

    def next(self):
        """ Python 2 iterator """
        if self._stop:
            raise StopIteration
        op = self._next_op()
        self._map[op]()
        return op

    def __next__(self):
        """ Python 3 iterator """
        return self.next()

    def _next_op(self):
        """ Get next operation """
        self.opcode = cord(self._co_code[self.lasti])
        self.opi = self.lasti
        self.lasti += 1
        if self.opcode >= HAVE_ARGUMENT:
            self._have_argument()

        if self.lasti >= self._size:
            self._stop = True

        return self.opcode

    def _pop_last_n(self, number):
        """ Pop last n objects from stack """
        return reversed([self.stack.pop() for _ in range(number)])

    def _have_argument(self):
        """ Read argument if op has argument """
        cod = self._co_code
        i = self.lasti
        self.oparg = cord(cod[i]) + cord(cod[i + 1]) * 256 + self._extended_arg
        self._extended_arg = 0
        self.lasti += 2

    def _create_map(self):
        """ Create map of functions """
        condition = lambda x, obj: (x[0] != '_' and
            hasattr(obj, '__call__') and 'opcode' in obj.__doc__)
        to_opcode = lambda x: x.upper().replace('__', '+')

        self._map = defaultdict(lambda: self.nop)
        self._extra = set()
        self._missing = set()
        self._supported = set()
        for name in dir(self):
            method = getattr(self, name)
            if condition(name, method):
                opcode = to_opcode(name)
                if opcode not in opmap:
                    self._extra.add(opcode)
                else:
                    self._map[opmap[opcode]] = method
                    self._supported.add(opcode)
        self._missing = (
            set(opmap.keys()) - self._supported - self._known_missing)

    @property
    def extra_opcode(self):
        """ Return opcode implemented by this class
            but not supported by Python """
        return self._extra

    @property
    def missing_opcode(self):
        """ Return opcode supported by Python
            but not implemented by this class """
        return self._missing

    def nop(self):
        """ NOP opcode """
        pass


class ExecInterpreter(Interpreter):
    """ Bytecode interpreter that executes it
        Currently, it is working only for Expressions
    """

    def _call(self, nargs, flags=0, nkw=0):
        """ Execute call """
        var, kwargs = [], {}
        if flags & CALL_FLAG_KW:
            kwargs = self.stack.pop()
        if flags & CALL_FLAG_VAR:
            var = self.stack.pop()
        for i in range(nkw):
            value = self.stack.pop()
            key = self.stack.pop()
            kwargs[key] = value
        args = list(self._pop_last_n(nargs))
        func = self.stack[-1]
        self.stack[-1] = func(*(args + var), **kwargs)

    def _binary(self, func):
        """ Execute binary operation """
        tos = self.stack.pop()
        self.stack[-1] = func(self.stack[-1], tos)

    def _inplace(self, func):
        """ Execute inplace operation """
        tos = self.stack.pop()
        self.stack[-1] = func(self.stack[-1], tos)

    def _unary(self, func):
        """ Execute unary operation """
        self.stack[-1] = func(self.stack[-1])

    def extended_arg(self):
        """ EXTENDED_ARG opcode """
        self._extended_arg = self.oparg * 65536

    def load_fast(self):
        """ LOAD_FAST opcode """
        self.stack.append(self._locals[self.varnames[self.oparg]])

    def load_global(self):
        """ LOAD_GLOBAL opcode """
        self.stack.append(self._globals[self.names[self.oparg]])

    def load_attr(self):
        """ LOAD_ATTR opcode """
        self.stack[-1] = getattr(self.stack[-1], self.names[self.oparg])

    def load_const(self):
        """ LOAD_CONST opcode """
        self.stack.append(self.consts[self.oparg])

    def load_name(self):
        """ LOAD_NAME opcode """
        self.stack.append(self.names[self.oparg])

    def build_tuple(self):
        """ BUILD_TUPLE opcode """
        self.stack.append(tuple(self._pop_last_n(self.oparg)))

    def build_list(self):
        """ BUILD_LIST opcode """
        self.stack.append(list(self._pop_last_n(self.oparg)))

    def build_map(self):
        """ BUILD_MAP opcode """
        self.stack.append({})

    def build_set(self):
        """ BUILD_SET opcode """
        self.stack.append(set(self._pop_last_n(self.oparg)))

    def store_map(self):
        """ STORE_MAP opcode """
        key, value = self.stack.pop(), self.stack.pop()
        self.stack[-1][key] = value

    def call_function(self):
        """ CALL_FUNCTION opcode """
        self._call(self.oparg & 0xff, flags=(self.opcode - CALL_FUNCTION) & 3,
                   nkw=(self.oparg >> 8) & 0xff)

    def call_function_var(self):
        """ CALL_FUNCTION_VAR opcode """
        self.call_function()

    def call_function_kw(self):
        """ CALL_FUNCTION_KW opcode """
        self.call_function()

    def call_function_var_kw(self):
        """ CALL_FUNCTION_VAR_KW opcode """
        self.call_function()

    def make_function(self):
        """ MAKE_FUNCTION opcode. Python 3 version """
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
        """ BUILD SLICE opcode """
        self.stack.append(slice(*self._pop_last_n(self.oparg)))

    def binary_add(self, func=lambda a, b: a + b):
        """ BINARY_ADD opcode """
        self._binary(func)

    def binary_and(self, func=lambda a, b: a & b):
        """ BINARY_AND opcode """
        self._binary(func)

    def binary_floor_divide(self, func=lambda a, b: a // b):
        """ BINARY_FLOOR_DIVIDE opcode """
        self._binary(func)

    def binary_lshift(self, func=lambda a, b: a << b):
        """ BINARY_LSHIFT opcode """
        self._binary(func)

    def binary_modulo(self, func=lambda a, b: a % b):
        """ BINARY_MODULO opcode """
        self._binary(func)

    def binary_multiply(self, func=lambda a, b: a * b):
        """ BINARY_MULTIPLY opcode """
        self._binary(func)

    def binary_or(self, func=lambda a, b: a | b):
        """ BINARY_OR opcode """
        self._binary(func)

    def binary_power(self, func=lambda a, b: a ** b):
        """ BINARY_POWER opcode """
        self._binary(func)

    def binary_rshift(self, func=lambda a, b: a >> b):
        """ BINARY_RSHIFT opcode """
        self._binary(func)

    def binary_subscr(self, func=lambda a, b: a[b]):
        """ BINARY_SUBSCR opcode """
        self._binary(func)

    def binary_subtract(self, func=lambda a, b: a - b):
        """ BINARY_SUBTRACT opcode """
        self._binary(func)

    def binary_true_divide(self, func=lambda a, b: a / b):
        """ BINARY_TRUE_DIVIDE opcode """
        self._binary(func)

    def binary_xor(self, func=lambda a, b: a ^ b):
        """ BINARY_XOR opcode """
        self._binary()

    def inplace_add(self, func=lambda a, b: a + b):
        """ INPLACE_ADD opcode """
        self._inplace(func)

    def inplace_and(self, func=lambda a, b: a & b):
        """ INPLACE_AND opcode """
        self._inplace(func)

    def inplace_floor_divide(self, func=lambda a, b: a // b):
        """ INPLACE_FLOOR_DIVIDE opcode """
        self._inplace(func)

    def inplace_lshift(self, func=lambda a, b: a << b):
        """ INPLACE_LSHIFT opcode """
        self._inplace(func)

    def inplace_modulo(self, func=lambda a, b: a % b):
        """ INPLACE_MODULO opcode """
        self._inplace(func)

    def inplace_multiply(self, func=lambda a, b: a * b):
        """ INPLACE_MULTIPLY opcode """
        self._inplace(func)

    def inplace_or(self, func=lambda a, b: a | b):
        """ INPLACE_OR opcode """
        self._inplace(func)

    def inplace_power(self, func=lambda a, b: a ** b):
        """ INPLACE_POWER opcode """
        self._inplace(func)

    def inplace_rshift(self, func=lambda a, b: a >> b):
        """ INPLACE_RSHIFT opcode """
        self._inplace(func)

    def inplace_subtract(self, func=lambda a, b: a - b):
        """ INPLACE_SUBTRACT opcode """
        self._inplace(func)

    def inplace_true_divide(self, func=lambda a, b: a / b):
        """ INPLACE_TRUE_DIVIDE opcode """
        self._inplace(func)

    def inplace_xor(self, func=lambda a, b: a ^ b):
        """ INPLACE_XOR opcode """
        self._inplace(func)

    def unary_invert(self, func=lambda a: ~a):
        """ UNARY_INVERT opcode """
        self._unary(func)

    def unary_negative(self, func=lambda a: -a):
        """ UNARY_NEGATIVE opcode """
        self._unary(func)

    def unary_not(self, func=lambda a: not a):
        """ UNARY_NOT opcode """
        self._unary(func)

    def unary_positive(self, func=lambda a: +a):
        """ UNARY_POSITIVE opcode """
        self._unary(func)

    def rot_two(self):
        """ ROT_TWO opcode """
        sta = self.stack
        sta[-1], sta[-2] = sta[-2], sta[-1]

    def rot_three(self):
        """ ROT_THREE opcode """
        sta = self.stack
        sta[-1], sta[-2], sta[-3] = sta[-2], sta[-3], sta[-1]

    def dup_top(self):
        """ DUP_TOP opcode """
        self.stack.append(self.stack[-1])

    def pop_top(self):
        """ POP_TOP opcode """
        self.stack.pop()

    def compare_op(self):
        """ COMPARE_OP opcode """
        tos, tos1 = self.stack.pop(), self.stack.pop()
        self.stack.append(COMPARE[self.oparg](tos1, tos))

    def jump_if_false_or_pop(self):
        """ JUMP_IF_FALSE_OR_POP opcode """
        tos = self.stack.pop()
        if not tos:
            self.lasti = self.oparg
            self.stack.append(tos)

    def jump_if_true_or_pop(self):
        """ JUMP_IF_TRUE_OR_POP opcode """
        tos = self.stack.pop()
        if tos:
            self.lasti = self.oparg
            self.stack.append(tos)

    def jump_forward(self):
        """ JUMP_FORWARD opcode """
        self.lasti += self.oparg

    def pop_jump_if_true(self):
        """ POP_JUMP_IF_TRUE opcode """
        if self.stack.pop():
            self.lasti = self.oparg

    def pop_jump_if_false(self):
        """ POP_JUMP_IF_FALSE opcode """
        if not self.stack.pop():
            self.lasti = self.oparg

    def jump_absolute(self):
        """ JUMP_ABSOLUTE opcode """
        self.lasti = self.oparg

    def get_iter(self):
        """ GET_ITER opcode """
        self.stack[-1] = iter(self.stack[-1])

    def list_append(self):
        """ LIST_APPEND opcode """
        tos = self.stack.pop()
        self.stack[-self.oparg].append(tos)

    def set_add(self):
        """ SET_ADD opcode """
        tos = self.stack.pop()
        self.stack[-self.oparg].add(tos)

    def map_add(self):
        """ MAP_ADD opcode """
        tos, tos1 = self.stack.pop(), self.stack.pop()
        self.stack[-self.oparg][tos] = tos1

    def for_iter(self):
        """ FOR_ITER opcode """
        try:
            self.stack.append(next(self.stack[-1]))
        except StopIteration:
            self.stack.pop()
            self.lasti += self.oparg

    def store_fast(self):
        """ STORE_FAST opcode """
        self._locals[self.varnames[self.oparg]] = self.stack.pop()

    def store_subscr(self):
        """ STORE_SUBSCR opcode """
        key, var, value = self.stack.pop(), self.stack.pop(), self.stack.pop()
        var[key] = value

    def store_name(self):
        """ STORE_NAME opcode """
        self._locals[self.names[self.oparg]] = self.stack.pop()

    def store_attr(self):
        """ STORE_ATTR opcode """
        var, value = self.stack.pop(), self.stack.pop()
        setattr(var, self.names[self.oparg], value)

    def store_global(self):
        """ STORE_GLOBAL opcode """
        self._globals[self.names[self.oparg]] = self.stack.pop()

    def delete_fast(self):
        """ DELETE_FAST opcode """
        del self._locals[self.varnames[self.oparg]]

    def delete_subscr(self):
        """ DELETE_SUBSCR opcode """
        key, var = self.stack.pop(), self.stack.pop()
        del var[key]

    def delete_name(self):
        """ DELETE_NAME opcode """
        del self._locals[self.names[self.oparg]]

    def delete_attr(self):
        """ DELETE_ATTR opcode """
        var = self.stack.pop()
        delattr(var, self.names[self.oparg])

    def delete_global(self):
        """ DELETE_GLOBAL opcode """
        del self._globals[self.names[self.oparg]]

    def print_expr(self):
        """ PRINT_EXPR opcode """
        self._result = self.stack.pop()


class Py2Interpreter(ExecInterpreter):

    def __init__(self, *args, **kwargs):
        self._known_missing = {
            "BUILD_CLASS", "EXEC_STMT", "LOAD_LOCALS", "PRINT_ITEM",
            "PRINT_ITEM_TO", "PRINT_NEWLINE", "PRINT_NEWLINE_TO", "STOP_CODE"
        }
        super(Py2Interpreter, self).__init__(*args, **kwargs)


    def make_function(self):
        """ MAKE_FUNCTION opcode """
        tup = tuple(self._pop_last_n(self.oparg))
        func = types.FunctionType(self.stack.pop(), f_globals)
        func.func_defaults = tup
        self.stack.append(func)

    def binary_divide(self):
        """ BINARY_DIVIDE opcode """
        self._binary(lambda a, b: a / b)

    def binary_true_divide(self,
            func=lambda a, b: (float(a) if isinstance(a, int) else a) / b):
        """ BINARY_TRUE_DIVIDE opcode """
        self._binary(func)

    def inplace_divide(self):
        """ INPLACE_DIVIDE opcode """
        self._inplace(lambda a, b: a / b)

    def inplace_true_divide(self,
            func=lambda a, b: (float(a) if isinstance(a, int) else a) / b):
        """ INPLACE_TRUE_DIVIDE opcode """
        self._inplace(func)

    def unary_positive(self, func=lambda a: repr(a)):
        """ UNARY_CONVERT opcode """
        self._unary(func)

    def slice__0(self):
        """ SLICE+0 opcode """
        self.stack[-1] = self.stack[-1][:]

    def slice__1(self):
        """ SLICE+1 opcode """
        tos = self.stack.pop()
        self.stack[-1] = self.stack[-1][tos:]

    def slice__2(self):
        """ SLICE+2 opcode """
        tos = self.stack.pop()
        self.stack[-1] = self.stack[-1][:tos]

    def slice__3(self):
        """ SLICE+3 opcode """
        tos = self.stack.pop()
        tos1 = self.stack.pop()
        self.stack[-1] = self.stack[-1][tos1:tos]

    def rot_four(self):
        """ ROT_FOUR opcode """
        sta = self.stack
        sta[-1], sta[-2], sta[-3], sta[-4] = sta[-2], sta[-3], sta[-4], sta[-1]

    def dup_topx(self):
        """ DUP_TOPX opcode """
        topx = list(self._pop_last_n(self.oparg))
        self.stack = self.stack + topx + topx

    def store_slice__0(self):
        """ STORE_SLICE+0 opcode """
        var, value = self.stack.pop(), self.stack.pop()
        var[:] = value

    def store_slice__1(self):
        """ STORE_SLICE+1 opcode """
        sli, var, value = self.stack.pop(), self.stack.pop(), self.stack.pop()
        var[sli:] = value

    def store_slice__2(self):
        """ STORE_SLICE+2 opcode """
        sli, var, value = self.stack.pop(), self.stack.pop(), self.stack.pop()
        var[:sli] = value

    def store_slice__3(self):
        """ STORE_SLICE+3 opcode """
        sta = self.stack
        sli2, sli1, var, value = sta.pop(), sta.pop(), sta.pop(), sta.pop()
        var[sli1:sli2] = value

    def delete_slice__0(self):
        """ DELETE_SLICE+0 opcode """
        var = self.stack.pop()
        del var[:]

    def delete_slice__1(self):
        """ STORE_SLICE+1 opcode """
        sli, var = self.stack.pop(), self.stack.pop()
        del var[sli:]

    def delete_slice__2(self):
        """ STORE_SLICE+2 opcode """
        sli, var = self.stack.pop(), self.stack.pop()
        del var[:sli]

    def delete_slice__3(self):
        """ STORE_SLICE+3 opcode """
        sli2, sli1, var = self.stack.pop(), self.stack.pop(), self.stack.pop()
        del var[sli1:sli2]


class Py3Interpreter(ExecInterpreter):

    def __init__(self, *args, **kwargs):
        self._known_missing = {
            "GET_YIELD_FROM_ITER", "BINARY_MATRIX_MULTIPLY", "GET_AWAITABLE",
            "GET_AITER", "GET_ANEXT", "BEFORE_ASYNC_WITH", "SETUP_ASYNC_WITH",
            "YIELD_FROM", "LOAD_BUILD_CLASS", "DELETE_DEREF",
            "LOAD_CLASSDEREF", "UNPACK_EX",
        }
        super(Py3Interpreter, self).__init__(*args, **kwargs)


    def dup_top_two(self):
        """ DUP_TOP_TWO opcode """
        top2 = list(self._pop_last_n(2))
        self.stack = self.stack + top2 + top2


class AlmostReadOnlyDict(dict):
    """ Use it to avoid changes on local variables """

    def __init__(self, *args, **kwargs):
        super(AlmostReadOnlyDict, self).__init__(*args, **kwargs)
        self.other = {}

    def __getitem__(self, item):
        if item in self.other:
            return self.other[item]
        return super(AlmostReadOnlyDict, self).__getitem__(item)

    def __setitem__(self, item, value):
        self.other[item] = value

    def __delitem__(self, item):
        if item in self.other:
            del self.other[item]

class FindFTrace(Interpreter):

    def __init__(self, *args, **kwargs):
        # Disable operations that may cause effect
        # Default
        # self.store_fast = self.nop
        self.store_subscr = self.nop
        # self.store_name = self.nop
        self.store_global = self.nop
        # self.delete_fast = self.nop
        self.delete_subscr = self.nop
        # self.delete_name = self.nop
        self.delete_attr = self.nop
        self.delete_global = self.nop
        self.print_expr = self.nop

        # Python 2
        self.store_slice__0 = self.nop
        self.store_slice__0 = self.nop
        self.store_slice__1 = self.nop
        self.store_slice__2 = self.nop
        self.store_slice__3 = self.nop
        self.delete_slice__0 = self.nop
        self.delete_slice__1 = self.nop
        self.delete_slice__2 = self.nop
        self.delete_slice__3 = self.nop

        super(FindFTrace, self).__init__(*args, **kwargs)

        self._locals = AlmostReadOnlyDict(self._locals)



    def store_attr(self):
        """ STORE_ATTR opcode """
        if self.names[self.oparg] == 'f_trace':
            self._stop = True
            if self.stack:
                self._result = self.stack.pop()
            else:
                self._result = True

VersionInterpreter = Py3Interpreter if PY3 else Py2Interpreter
FTraceExec = type(
    default_string('FTraceExec'), (FindFTrace, VersionInterpreter), {})


def get_f_trace(code, loc, glob):
    interpreter = FTraceExec(code, loc, glob)
    for operation in interpreter:
        pass
    return interpreter._result


def find_f_trace(code, loc, glob, lasti):
    if 'f_trace' not in code.co_names:
        return False
    interpreter = FindFTrace(code, loc, glob)
    for operation in interpreter:
        pass
    if not interpreter._result:
        return False

    line_by_offset = OrderedDict(dis.findlinestarts(code))
    last_line, last_offset = 0, 0
    for offset, line in items(line_by_offset):
        if offset >= interpreter.opi:
            return lasti == last_offset
        last_line, last_offset = line, offset
    return False
