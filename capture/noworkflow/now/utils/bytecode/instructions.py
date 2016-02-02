# Copyright (c) 2016 Universidade Federal Fluminense (UFF)
# Copyright (c) 2016 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""Define bytecode instructions"""
from __future__ import (absolute_import, print_function,
                        division, unicode_literals)


class Instruction(object):                                                       # pylint: disable=too-many-instance-attributes, too-few-public-methods
    """Bytecode Instruction"""

    def __init__(self, opname, opcode, arg, argval, argrepr, offset,             # pylint: disable=too-many-arguments
                 starts_line, is_jump_target, line):
        self.opname = opname
        self.opcode = opcode
        self.arg = arg
        self.argval = argval
        self.argrepr = argrepr
        self.offset = offset
        self.starts_line = starts_line
        self.is_jump_target = is_jump_target
        self.lineno_width = 3
        self.mark_as_current = False
        self.line = line
        self.extra = None

    def __repr__(self):
        fields = []
        # Column: Source code line number
        if self.lineno_width:
            if self.starts_line is not None:
                lineno_fmt = "%%%dd" % self.lineno_width
                fields.append(lineno_fmt % self.starts_line)
            else:
                fields.append(" " * self.lineno_width)
        # Column: Current instruction indicator
        if self.mark_as_current:
            fields.append("-->")
        else:
            fields.append("   ")
        # Column: Jump target marker
        if self.is_jump_target:
            fields.append(">>")
        else:
            fields.append("  ")
        # Column: Instruction offset from start of code sequence
        fields.append(repr(self.offset).rjust(4))
        # Column: Opcode name
        fields.append(self.opname.ljust(20))
        # Column: Opcode argument
        if self.arg is not None:
            fields.append(repr(self.arg).rjust(5))
            # Column: Opcode argument details
            if self.argrepr:
                fields.append("(" + self.argrepr + ")")
        else:
            fields.append(" " * 5)
        if self.extra:
            fields.append("| {}".format(self.extra))
        return " ".join(fields).rstrip()
