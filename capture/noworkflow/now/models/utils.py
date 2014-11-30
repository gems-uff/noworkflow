# Copyright (c) 2014 Universidade Federal Fluminense (UFF)
# Copyright (c) 2014 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.

from __future__ import (absolute_import, print_function,
                        division, unicode_literals)

from datetime import datetime


FORMAT = '%Y-%m-%d %H:%M:%S.%f'


def calculate_duration(obj):
    return int((
        datetime.strptime(obj['finish'], FORMAT) -
        datetime.strptime(obj['start'], FORMAT)
    ).total_seconds() * 1000000)
