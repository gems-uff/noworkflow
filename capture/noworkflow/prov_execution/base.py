# Copyright (c) 2014 Universidade Federal Fluminense (UFF), Polytechnic Institute of New York University.
# This file is part of noWorkflow. Please, consult the license terms in the LICENSE file.

from __future__ import absolute_import

try:
    import __builtin__ as builtins
except ImportError:
    import builtins
import os
import sys
from datetime import datetime
from collections import defaultdict
from .. import persistence


class ExecutionProvider(object):

    def __init__(self, metascript, depth_context, depth_threshold):
        self.enabled = False  # Indicates when activations should be collected (only after the first call to the script)
        self.script = metascript['path']
        self.depth_context = depth_context  # which function types ('non-user' or 'all') should be considered for the threshold
        self.depth_threshold = depth_threshold  # how deep we want to go when capturing function activations?
        self.metascript = metascript
        self.event_map = defaultdict(lambda: self.trace_empty, {})
   
    def trace_empty(self, frame, event, arg):
        pass

    def tracer(self, frame, event, arg):
        self.event_map[event](frame, event, arg)

    def store(self):
        pass

    def teardown(self):
        sys.setprofile(None)
        sys.settrace(None)

    def tearup(self):
        pass


class StoreOpenMixin(ExecutionProvider):

    def __init__(self, *args):
        super(StoreOpenMixin, self).__init__(*args)
        persistence.std_open = open
        builtins.open = self.new_open(open)

    def add_file_access(self, file_access):
        'The class that uses this mixin must override this method'
        pass

    def new_open(self, old_open):
        'Wraps the open buildin function to register file access'
        def open(name, *args, **kwargs):  # @ReservedAssignment
            if self.enabled:
                file_access = {  # Create a file access object with default values
                    'name': name,
                    'mode': 'r',
                    'buffering': 'default',
                    'content_hash_before': None,
                    'content_hash_after': None,
                    'timestamp': datetime.now()
                }

                if os.path.exists(name):  # Read previous content if file exists
                    with old_open(name, 'rb') as f:
                        file_access['content_hash_before'] = persistence.put(f.read())

                file_access.update(kwargs)  # Update with the informed keyword arguments (mode and buffering)
                if len(args) > 0:  # Update with the informed positional arguments
                    file_access['mode'] = args[0]
                elif len(args) > 1:
                    file_access['buffering'] = args[1]

                self.add_file_access(file_access)
            return old_open(name, *args, **kwargs)

        return open

    def teardown(self):
        'Restores default open'
        super(StoreOpenMixin, self).teardown()
        builtins.open = persistence.std_open
