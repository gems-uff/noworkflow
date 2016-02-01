# Copyright (c) 2016 Universidade Federal Fluminense (UFF)
# Copyright (c) 2016 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""'%now_ls_magic' magic"""
from __future__ import (absolute_import, print_function,
                        division, unicode_literals)

from ...utils.formatter import PrettyLines
from .command import IpythonCommandMagic


class NowLsMagic(IpythonCommandMagic):
    """Return the list of noWorkflow magics"""

    def execute(self, func, line, cell, magic_cls):
        cline, ccell = "%", "%%"
        magics = magic_cls.now_magics
        out = ["Line magics:",
               cline + ("  " + cline).join(sorted(magics["line"])),
               "",
               "Cell magics:",
               ccell + ("  " + ccell).join(sorted(magics["cell"]))]
        return PrettyLines(out)
