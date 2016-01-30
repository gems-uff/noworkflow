# Copyright (c) 2016 Universidade Federal Fluminense (UFF)
# Copyright (c) 2016 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""Collect deployment provenance"""
from __future__ import (absolute_import, print_function,
                        division, unicode_literals)


def collect_provenance(metascript):
    metascript.deployment.collect_provenance(metascript)
