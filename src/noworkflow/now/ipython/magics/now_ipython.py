# Copyright (c) 2016 Universidade Federal Fluminense (UFF)
# Copyright (c) 2016 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""'%now_ip' magic"""
from __future__ import (absolute_import, print_function,
                        division, unicode_literals)

from .command import IpythonCommandMagic


class NowIpython(IpythonCommandMagic):
    """Return the noWorkflow IPython Module

       Equivalent to:
       In [1]: import noworkflow.now.ipython as nip
          ...: nip
    """

    def execute(self, func, line, cell, magic_cls):
        from ... import ipython as nip
        return nip
