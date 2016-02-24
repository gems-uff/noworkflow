# Copyright (c) 2016 Universidade Federal Fluminense (UFF)
# Copyright (c) 2016 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""Bytecode transformers"""

import array

from collections import Counter
from types import CodeType

from .dis import code_dis_sorted_line, findlinestarts

from ..cross_version import PY3


def reconstruct_lnotab(first_line, offsets, lines):
    """Reconstruct lnotab according to Python/Objects/lnotab_notes.txt


    Arguments:
    first_line -- first_line in code object (co_firstlineno)
    offsets -- sorted offsets list
    lines -- sorted lines list
    """
    current_offset, current_line = 0, first_line
    new_lnotab = []
    for offset, line in zip(offsets, lines):
        new_offset = offset - current_offset
        while new_offset > 255:
            new_lnotab.append(255)
            new_lnotab.append(0)
            new_offset -= 255
        new_lnotab.append(new_offset)
        new_line = line - current_line
        while new_line > 255:
            new_lnotab.append(255)
            new_lnotab.append(0)
            new_line -= 255
        new_lnotab.append(new_line)
        current_offset, current_line = offset, line
    return array.array('B', new_lnotab).tostring()


def original_line_offsets(code, codes, codes_offsets, codes_lines):
    """Find original offsets and lines


    Arguments:
    code -- CodeType object
    codes_offsets -- dict to be populated with code objects mapped to code ids
    codes_offsets -- dict to be populated with offset lists mapped to code ids
    codes_lines -- dict to be populated with line lists mapped to code ids
    """
    codes[id(code)] = code # necessary to keep reference to code objects
    offsets = codes_offsets[id(code)] = []
    lines = codes_lines[id(code)] = []
    # ToDo: submit a patch to Python to optimize findlinestarts with iters
    for addr, lineno in findlinestarts(code):
        offsets.append(addr)
        lines.append(lineno)

    for const in code.co_consts:
        if isinstance(const, CodeType):
            original_line_offsets(const, codes, codes_offsets, codes_lines)


def recreate_code(code, codes_offsets, codes_lines):
    """Recreate code with new lnotab


    Arguments:
    code -- original code object
    codes_offsets -- updated list of offsets
    codes_lines -- updated list of lines
    """
    offsets = codes_offsets[id(code)]
    lines = codes_lines[id(code)]
    new_lnotab = reconstruct_lnotab(code.co_firstlineno, offsets, lines)
    new_consts = []
    for const in code.co_consts:
        if isinstance(const, CodeType):
            new_consts.append(recreate_code(const, codes_offsets, codes_lines))
        else:
            new_consts.append(const)

    if PY3:
        new_code = CodeType(
            code.co_argcount, code.co_kwonlyargcount, code.co_nlocals,
            code.co_stacksize, code.co_flags, code.co_code, tuple(new_consts),
            code.co_names, code.co_varnames, code.co_filename, code.co_name,
            code.co_firstlineno, new_lnotab, code.co_freevars, code.co_cellvars
        )
    else:
        new_code = CodeType(
            code.co_argcount, code.co_nlocals,
            code.co_stacksize, code.co_flags, code.co_code, tuple(new_consts),
            code.co_names, code.co_varnames, code.co_filename, code.co_name,
            code.co_firstlineno, new_lnotab, code.co_freevars, code.co_cellvars
        )
    return new_code


def insert_new_lines(compiled, process):                                         # pylint: disable=too-many-locals
    """Insert new line events to bytecode
    Return line multiplier and new code

    Arguments:
    compiled -- original code
    process -- process(inst, code, offsets, lines) function which should add
               offsets and lines according to inst
    """
    codes = {}
    codes_offsets = {}
    codes_lines = {}

    original_line_offsets(compiled, codes, codes_offsets, codes_lines)

    for code, inst in code_dis_sorted_line(compiled, recurse=True):
        lines = codes_lines[id(code)]
        offsets = codes_offsets[id(code)]
        process(inst, code, offsets, lines)

    # Create fake line numbers: lines should be unique
    new_codes_lines = {}
    size = max(Counter(lines).most_common(1)[0][1]
               for lines in codes_lines.values())

    for code_id, lines in codes_lines.items():
        new_lines = []
        last = -1
        for line in lines:
            if line != last:
                offset = 0
            new_lines.append(line * size + offset)
            offset += 1
            last = line
        new_codes_lines[code_id] = new_lines

    return size, recreate_code(compiled, codes_offsets, new_codes_lines)
