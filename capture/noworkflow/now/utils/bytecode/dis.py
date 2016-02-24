# Copyright (c) 2016 Universidade Federal Fluminense (UFF)
# Copyright (c) 2016 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""Cross version dis"""
from __future__ import (absolute_import, print_function,
                        division, unicode_literals)

import dis as _dis
import sys
import types
from collections import OrderedDict

from .interpreter import InstructionInterpreter


HAVE_CODE = (types.MethodType, types.FunctionType, types.CodeType, type)
PY3 = sys.version_info >= (3, 0)


def _try_compile(source, name, tries=None, compiler=None):
    """Atempt to compile with <compiler> for <tries> modes"""
    if tries is None:
        tries = ["eval", "exec"]
    if not tries:
        raise ValueError("syntax error in passed string")
    try:
        if not compiler:
            return compile(source, name, tries[0])
        else:
            return compiler(source, name, tries[0])
    except SyntaxError:
        return _try_compile(source, name, tries, compiler)


def _get_code_object(obj, compiler=None):
    """Return code object"""
    if isinstance(obj, types.FrameType):  # Frame
        return ("code", obj.f_code)
    if not PY3 and isinstance(obj, types.InstanceType):  # Instance              # pylint: disable=no-member
        obj = obj.__class__
    if hasattr(obj, "__func__"):  # Method
        obj = obj.__func__
    if hasattr(obj, "gi_code"):  # Generator
        obj = obj.gi_code
    if hasattr(obj, "im_func"):  # Function Python 2
        obj = obj.im_func
    if hasattr(obj, "func_code"):  # Function Python 2
        obj = obj.func_code
    if hasattr(obj, "__code__"):  # Function
        obj = obj.__code__
    if isinstance(obj, str):  # Soruce code
        obj = _try_compile(obj, "<string>", compiler=compiler)
    if hasattr(obj, "co_code"):  # Code
        return ("code", obj)
    if hasattr(obj, "__dict__"):  # Class or module
        return ("dict", obj)
    if PY3 and isinstance(obj, (bytes, bytearray)):  # Raw bytecode
        return ("bytes", obj)
    raise TypeError("get_code_object() can not handle '{}' objects".format(
        type(obj).__name__))


def _byte_instructions(code, lasti=-1, varsn=None, names=None, consts=None,      # pylint: disable=too-many-arguments
                       cells=None, linestarts=None, line_offset=0):
    """Generator for byte code instructions
    Check if it starts a line
    """
    interpreter = InstructionInterpreter(code, varsn, names, consts,
                                         cells, linestarts, line_offset)
    # Omit line number
    show_lineno = linestarts is not None
    lineno_width = 3 if show_lineno else 0

    for inst in interpreter:
        inst.lineno_width = lineno_width
        inst.new_source_line = (show_lineno and
                                inst.starts_line is not None and
                                inst.offset > 0)
        inst.is_current_inst = inst.offset == lasti
        yield inst


def _instructions(code, lasti=-1):
    """Generator for code instructions"""
    cell_names = code.co_cellvars + code.co_freevars
    linestarts = OrderedDict(_dis.findlinestarts(code))
    insts = _byte_instructions(
        code.co_code, lasti, code.co_varnames, code.co_names,
        code.co_consts, cell_names, linestarts)

    for inst in insts:
        yield inst


def idis(obj=None, compiler=None, outfile=None):
    """Disassemble objects"""
    typ, code = _get_code_object(obj, compiler)
    if typ == "code":
        for inst in _instructions(code):
            yield inst
    elif typ == "bytes":
        for inst in _byte_instructions(code,):
            yield inst
    elif typ == "dict":
        items = sorted(code.__dict__.items())
        for name, attr in items:
            if isinstance(attr, HAVE_CODE):
                print("Disassembly of %s:" % name, file=outfile)
                try:
                    for inst in idis(attr, compiler=compiler, outfile=outfile):
                        yield inst
                except TypeError as msg:
                    print("Sorry:", msg, file=outfile)
                print(file=outfile)


def _visit(obj, visitor, compiler=None, recurse=False):
    """Recursively disassemble"""
    for _, inst in _visit_with_code(obj, visitor, compiler, recurse):
        yield inst


def _visit_with_code(obj, visitor, compiler=None, recurse=False):
    """Recursively disassemble"""
    typ, obj = _get_code_object(obj, compiler)
    for inst in visitor(obj, compiler=compiler):
        yield obj, inst
    if typ == "code" and recurse:
        for constant in obj.co_consts:
            if type(constant) is type(obj):
                for code, inst in _visit_with_code(constant, visitor,
                                                   compiler, recurse):
                    yield code, inst


def instruction_dis(compiled, compiler=None, recurse=False):
    """Return dis of compiled code"""
    return list(_visit(compiled, idis, compiler, recurse))


def code_dis(compiled, compiler=None, recurse=False):
    """Return dis of compiled code"""
    return list(_visit_with_code(compiled, idis, compiler, recurse))


def instruction_dis_sorted_by_line(compiled, compiler=None, recurse=False):
    """Return dis sorted by line of compiled code"""
    instructions = instruction_dis(compiled, compiler, recurse)
    return sorted(instructions, key=lambda x: (x.line, x.offset))


def code_dis_sorted_line(compiled, compiler=None, recurse=False):
    """Return dis sorted by line of compiled code"""
    instructions = code_dis(compiled, compiler, recurse)
    return sorted(instructions, key=lambda x: (x[1].line, x[1].offset))


findlinestarts = _dis.findlinestarts                                             # pylint: disable=invalid-name
