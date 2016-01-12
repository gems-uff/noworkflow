# Copyright (c) 2015 Universidade Federal Fluminense (UFF)
# Copyright (c) 2015 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""Command Types"""

import argparse

from ..persistence import persistence


def trial_reference(string):
    """Check if argument is a trial reference"""
    trial_id = persistence.load_trial_id(string)
    if trial_id is None:
        raise argparse.ArgumentTypeError(
            "{} is not a trial reference".format(string))
    return trial_id
