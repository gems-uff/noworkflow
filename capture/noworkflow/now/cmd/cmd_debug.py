# Copyright (c) 2016 Universidade Federal Fluminense (UFF)
# Copyright (c) 2016 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""'now debug' command"""
from __future__ import (absolute_import, print_function,
                        division, unicode_literals)

from .cmd_run import Run


class Debug(Run):
    """Debug a script collecting its provenance
       This command is similar to Run, but defines different variables"""

    def __init__(self, *args, **kwargs):
        super(Debug, self).__init__(*args, **kwargs)
        self.default_context = "package"
        self.default_call_storage_frequency = 1
        self.default_save_frequency = 1000
        self.default_execution_provenance = "Tracer"
