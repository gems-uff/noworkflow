# Copyright (c) 2016 Universidade Federal Fluminense (UFF)
# Copyright (c) 2016 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""Define MetaProfiler

Use it to profile noWorkflow itself.
It is disabled by deault. To enabled, change active to True
"""
from __future__ import (absolute_import, print_function,
                        division, unicode_literals)

import csv
import os

from collections import defaultdict
from datetime import datetime
from functools import wraps


class MetaProfiler(object):                                                      # pylint: disable=too-few-public-methods
    """Profile noWorkflow itself"""

    def __init__(self, active=False):
        self.file = "nowtime.csv"
        self.active = active
        self.order = [
            "cmd",
            "definition",
            "deployment", "environment", "modules",
            "execution",
            "storage"
        ]
        self.data = defaultdict(float)

    def __call__(self, typ):
        def dec(func):
            """Return decorator that stores the duration in typ"""
            if typ not in self.order:
                self.order.append(typ)

            @wraps(func)
            def wrapper(*args, **kwargs):
                """Capture duration of function"""
                before = datetime.now()
                result = func(*args, **kwargs)
                after = datetime.now()
                self.data[typ] += (after - before).total_seconds()
                return result
            return wrapper
        return dec

    def save(self):
        """Save durations"""
        if self.active:
            row = [self.data[name] for name in self.order]
            rows = []
            if not os.path.exists(self.file):
                rows.append(self.order)
            rows.append(row)

            with open(self.file, "a") as fil:
                writter = csv.writer(fil)
                writter.writerows(rows)

meta_profiler = MetaProfiler(active=False)                                       # pylint: disable=invalid-name
