# Copyright (c) 2016 Universidade Federal Fluminense (UFF)
# Copyright (c) 2016 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.

from __future__ import (absolute_import, print_function,
                        division, unicode_literals)
"""
Supporting infrastructure to run scientific experiments without a
scientific workflow management system.
"""
from noworkflow.now.cmd import main
from noworkflow.now.utils.functions import version


def load_ipython_extension(ipython):
    from .now.ipython import init
    init(ipython=ipython)


if __name__ == "__main__":
    main()

__version__ = version()
