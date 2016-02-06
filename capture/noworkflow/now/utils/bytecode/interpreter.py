# Copyright (c) 2016 Universidade Federal Fluminense (UFF)
# Copyright (c) 2016 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""Define bytecode interpreter that supports iteration on bytecode"""
from __future__ import (absolute_import, print_function,
                        division, unicode_literals)

import dis
from dis import opmap

from collections import defaultdict
from opcode import HAVE_ARGUMENT, cmp_op

from .instructions import Instruction


CALL_FUNCTIONS = {
    opmap["CALL_FUNCTION"], opmap["CALL_FUNCTION_VAR"],
    opmap["CALL_FUNCTION_KW"], opmap["CALL_FUNCTION_VAR_KW"]
}

PRINT_ITEMS = set()
if "PRINT_ITEM" in opmap:
    PRINT_ITEMS.add(opmap["PRINT_ITEM"])
    PRINT_ITEMS.add(opmap["PRINT_ITEM_TO"])

PRINT_NEW_LINES = set()
if "PRINT_NEWLINE" in opmap:
    PRINT_NEW_LINES.add(opmap["PRINT_NEWLINE"])
    PRINT_NEW_LINES.add(opmap["PRINT_NEWLINE_TO"])

SETUP_WITH = {opmap["SETUP_WITH"], }
WITH_CLEANUP = {opmap.get("WITH_CLEANUP") or opmap.get("WITH_CLEANUP_START"), }
SETUP_ASYNC_WITH = set()
if "SETUP_ASYNC_WITH" in opmap:
    SETUP_ASYNC_WITH.add(opmap["SETUP_ASYNC_WITH"])

IMPORTS = {opmap["IMPORT_NAME"], opmap["IMPORT_FROM"]}

IMPORT_NAMES = {opmap["IMPORT_NAME"],}

FOR_ITERS = {opmap["FOR_ITER"],}
GET_ITERS = {opmap["GET_ITER"],}


def cord(value):
    """Convert (str or int) to ord"""
    if isinstance(value, str):
        return ord(value)
    return value


class ListAccessor(object):                                                      # pylint: disable=too-few-public-methods
    """List Proxy. Return value on x[i] and tuple on x(i)"""

    def __init__(self, values, repr_is_val=True):
        self.values = values
        self.repr_is_val = repr_is_val

    def __getitem__(self, index):
        if self.values is not None:
            return self.values[index]
        return index

    def __call__(self, index):
        argval = self[index]
        if self.repr_is_val and self.values is not None:
            argrepr = argval
        else:
            argrepr = repr(argval)
        return argval, argrepr


class Interpreter(object):                                                       # pylint: disable=too-many-instance-attributes
    """Bytecode iterator"""

    def __init__(self, co_code, varnames=None, names=None, constants=None,       # pylint: disable=too-many-arguments
                 cells=None, linestarts=None, line_offset=0):
        self.lasti = 0
        self.opi = 0
        self._extended_arg = 0

        self._co_code = co_code
        self.varnames = ListAccessor(varnames)
        self.names = ListAccessor(names)
        self.consts = ListAccessor(constants, repr_is_val=False)
        self.cells = ListAccessor(cells)
        self.linestarts = linestarts
        self.line_offset = line_offset

        self._size = len(co_code)

        self.opcode = None
        self.oparg = 0

        self._stop = False

        self._map = {}
        self._extra = set()
        self._missing = set()
        self._supported = set()
        if not hasattr(self, "_known_missing"):
            self._known_missing = set()

        self._create_map()

    def __iter__(self):
        """Restart iterator"""
        self._stop = False
        return self

    def __call__(self, lasti=0, extended_arg=0):
        self.lasti = lasti
        self._extended_arg = extended_arg

    def next(self):
        """Python 2 iterator"""
        if self._stop:
            raise StopIteration
        opcode = self._next_op()
        self._map[opcode]()
        return opcode

    def __next__(self):
        """Python 3 iterator"""
        return self.next()

    def _next_op(self):
        """Get next operation"""
        self._set_opcode()
        if self.opcode >= HAVE_ARGUMENT:
            self._have_argument()

        if self.lasti >= self._size:
            self._stop = True

        return self.opcode

    def _set_opcode(self):
        """Get op from code"""
        self.oparg = None
        self.opcode = cord(self._co_code[self.lasti])
        self.opi = self.lasti
        self.lasti += 1

    def _have_argument(self):
        """Read argument if op has argument"""
        cod = self._co_code
        i = self.lasti
        self.oparg = cord(cod[i]) + cord(cod[i + 1]) * 256 + self._extended_arg
        self._extended_arg = 0
        self.lasti += 2

    def _create_map(self):
        """Create map of functions"""
        condition = lambda x, obj: (
            x[0] != "_" and hasattr(obj, "__call__") and
            obj.__doc__ is not None and "opcode" in obj.__doc__)
        to_opcode = lambda x: x.upper().replace("__", "+")

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
        """Return opcode implemented by this class
        but not supported by Python
        """
        return self._extra

    @property
    def missing_opcode(self):
        """Return opcode supported by Python
        but not implemented by this class"""
        return self._missing

    def nop(self):
        """NOP opcode"""
        pass


class InstructionInterpreter(Interpreter):
    """Mix Python3 dis._get_instructions_bytes with Python2 dis.disassemble"""

    def __init__(self, *args, **kwargs):
        super(InstructionInterpreter, self).__init__(*args, **kwargs)

        self._labels = dis.findlabels(self._co_code)

        self.starts_line = None
        self.is_jump_target = False
        self.argval = None
        self.argrepr = None
        self.current_line = -1

    def _set_opcode(self):
        super(InstructionInterpreter, self)._set_opcode()
        if self.linestarts is not None:
            self.starts_line = self.linestarts.get(self.opi, None)
            if self.starts_line is not None:
                self.starts_line += self.line_offset
                self.current_line = self.starts_line
        self.is_jump_target = self.opi in self._labels

    def _have_argument(self):
        super(InstructionInterpreter, self)._have_argument()
        opcode = self.opcode
        arg = argval = self.oparg
        argrepr = ""
        if opcode in dis.hasconst:
            argval, argrepr = self.consts(arg)
        elif opcode in dis.hasname:
            argval, argrepr = self.names(arg)
        elif opcode in dis.hasjrel:
            argval = self.lasti + arg
            argrepr = "to " + repr(argval)
        elif opcode in dis.haslocal:
            argval, argrepr = self.varnames(arg)
        elif opcode in dis.hascompare:
            argval = cmp_op[arg]
            argrepr = argval
        elif opcode in dis.hasfree:
            argval, argrepr = self.cells(arg)
        elif opcode in CALL_FUNCTIONS:
            argrepr = "%d positional, %d keyword pair" % (
                cord(self._co_code[self.lasti - 2]),
                cord(self._co_code[self.lasti - 1]))
        self.argval, self.argrepr = argval, argrepr

    def next(self):
        super(InstructionInterpreter, self).next()
        return Instruction(
            dis.opname[self.opcode], self.opcode, self.oparg, self. argval,
            self.argrepr, self.opi, self.starts_line, self.is_jump_target,
            self.current_line)
