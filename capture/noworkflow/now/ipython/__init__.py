# Copyright (c) 2016 Universidade Federal Fluminense (UFF)
# Copyright (c) 2016 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""IPython Module"""
from __future__ import (absolute_import, print_function,
                        division)


from ..persistence.models import *                                               # pylint: disable=wildcard-import
from ..persistence import persistence_config, relational, content


def init(path=None, ipython=None):
    """Initiate noWorkflow extension.
    Load D3, IPython magics, and connect to database


    Keyword Arguments:
    path -- database path (default=current directory)
    ipython -- IPython object (default=None)
    """

    import os
    from .magics import register_magics
    try:
        from .hierarchymagic import load_ipython_extension as load_hierarchy
        load_hierarchy(ipython)
    except ImportError:
        print("Warning: Sphinx is not installed. Dot "
              "graphs won't work")

    register_magics(ipython)

    if path is None:
        path = os.getcwd()
    persistence_config.connect(path)

    return u"ok"
