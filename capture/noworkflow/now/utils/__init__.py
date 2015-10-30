# Copyright (c) 2015 Universidade Federal Fluminense (UFF)
# Copyright (c) 2015 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""Define utility functions"""
from __future__ import (absolute_import, print_function,
                        division, unicode_literals)


from .consts import FORMAT
from .data import concat_iter, OrderedCounter, hashabledict
from .functions import wrap, resource, calculate_duration
from .io import redirect_output, print_msg, print_fn_msg, verbose
from .metaprofiler import meta_profiler
