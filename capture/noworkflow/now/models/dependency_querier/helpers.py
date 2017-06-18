# Copyright (c) 2017 Universidade Federal Fluminense (UFF)
# Copyright (c) 2017 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""Helpers"""
import bisect
from collections import namedtuple


class Arrow(object):
    """Represent an arrow with a label"""
    # pylint: disable=too-few-public-methods
    def __init__(self, type_, time_restriction=None, part=None):
        self.label = part or type_
        self.type = type_
        self.time_restriction = time_restriction
        self.marked = False

    def __repr__(self):
        if not self.marked:
            return '[label="{}"]'.format(self.label)
        return '[label="{}" color="blue"]'.format(self.label)


Context = namedtuple("Context", "element moment block_set")


class ValueState(dict):
    """Represent the state of a value at a given moment"""
    def __init__(self, *args, **kwargs):
        super(ValueState, self).__init__(*args, **kwargs)
        self.ordered_list = []

    def __setitem__(self, moment, value):
        super(ValueState, self).__setitem__(moment, value)
        bisect.insort_right(self.ordered_list, moment)

    def current_value(self, moment):
        """Get value at a specific moment"""
        return self.current_pair(moment)[0]

    def current_pair(self, moment):
        """Get value and its moment at a specific moment"""
        index = bisect.bisect_right(self.ordered_list, moment) - 1
        if index == -1:
            return None, None
        the_moment = self.ordered_list[index]
        return self[the_moment], the_moment
