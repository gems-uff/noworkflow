# Copyright (c) 2014 Universidade Federal Fluminense (UFF)
# Copyright (c) 2014 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.

from __future__ import (absolute_import, print_function,
                        division, unicode_literals)

import os
import sys
from datetime import datetime
from collections import defaultdict

from .argument_captors import ArgumentCaptor
from ..persistence import persistence
from ..cross_version import builtins
from ..prov_definition.definition import Definition


class ExecutionProvider(object):

    def __init__(self, metascript):
        # Indicates when activations should be collected
        #   (only after the first call to the script)
        self.enabled = False
        # User files
        self.script = metascript.path
        self.paths = metascript.paths
        # Which function types ('main', 'package' or 'all')
        #   should be considered for the threshold
        self.context = metascript.context
        # How deep we want to go when capturing function activations?
        self.depth_threshold = metascript.depth
        # How deep we want to go beyond our context
        self.non_user_depth_threshold = metascript.non_user_depth

        # Object serializer function
        self.serialize = metascript.serialize

        self.metascript = metascript
        self.trial_id = metascript.trial_id
        self.event_map = defaultdict(lambda: self.trace_empty, {})
        self.default_profile = sys.getprofile()
        self.default_trace = sys.gettrace()

        self.argument_captor = ArgumentCaptor(self)

    def trace_empty(self, frame, event, arg):
        pass

    def tracer(self, frame, event, arg):
        self.event_map[event](frame, event, arg)

    def store(self, partial=False):
        pass

    def teardown(self):
        self.enabled = False

    def tearup(self):
        pass
