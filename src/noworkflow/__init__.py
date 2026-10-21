# Copyright (c) 2016 Universidade Federal Fluminense (UFF)
# Copyright (c) 2016 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.

"""
Supporting infrastructure to run scientific experiments without a
scientific workflow management system.
"""

from __future__ import absolute_import, division, print_function, unicode_literals

import sys

from noworkflow.now.cmd import main
from noworkflow.now.utils.functions import version


def load_ipython_extension(ipython):
    from .now.ipython import init

    init(ipython=ipython)


if __name__ == "__main__":
    sys.exit(main())

__version__ = version()
