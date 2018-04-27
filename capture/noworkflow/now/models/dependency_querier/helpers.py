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


Context = namedtuple("Context", "element checkpoint block_set")


class ValueState(dict):
    """Represent the state of a value at a given checkpoint"""
    def __init__(self, *args, **kwargs):
        super(ValueState, self).__init__(*args, **kwargs)
        self.ordered_list = []

    def __setitem__(self, checkpoint, value):
        super(ValueState, self).__setitem__(checkpoint, value)
        bisect.insort_right(self.ordered_list, checkpoint)

    def current_value(self, checkpoint):
        """Get value at a specific checkpoint"""
        return self.current_pair(checkpoint)[0]

    def current_pair(self, checkpoint):
        """Get value and its checkpoint at a specific checkpoint"""
        index = bisect.bisect_right(self.ordered_list, checkpoint) - 1
        if index == -1:
            return None, None
        the_checkpoint = self.ordered_list[index]
        return self[the_checkpoint], the_checkpoint
