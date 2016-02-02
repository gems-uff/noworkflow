# Copyright (c) 2016 Universidade Federal Fluminense (UFF)
# Copyright (c) 2016 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""Define f_trace related interpreters and functions"""
from __future__ import (absolute_import, print_function,
                        division, unicode_literals)

from future.utils import bytes_to_native_str as n

from .code_interpreter import CodeInterpreter, PyInterpreter


class AlmostReadOnlyDict(dict):
    """Use it to avoid changes on the original dict"""

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


class FindFTrace(CodeInterpreter):                                               # pylint: disable=too-many-instance-attributes
    """Find <expr>.f_trace attribution"""

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
        self._globals = AlmostReadOnlyDict(self._globals)

    def store_attr(self):
        """STORE_ATTR opcode"""
        if self.names[self.oparg] == "f_trace":
            self._stop = True
            self.result = self.stack.pop() if self.stack else True


FTraceExe = type(n(b"FTraceExe"), (FindFTrace, PyInterpreter), {})               # pylint: disable=invalid-name


def get_f_trace(code, loc, glob):
    """Get frame from frame.f_trace attribution"""
    interpreter = FTraceExe(code, loc, glob)
    interpreter.execute()
    return interpreter.result


def find_f_trace(code, loc, glob, lasti):
    """Check if code has frame.f_trace attribution"""
    if "f_trace" not in code.co_names:
        return False
    interpreter = FindFTrace(code, loc, glob)
    interpreter.execute()
    if not interpreter.result:
        return False

    last_offset = 0
    for offset in interpreter.linestarts:
        if offset >= interpreter.opi:
            return lasti == last_offset
        last_offset = offset
    return False
