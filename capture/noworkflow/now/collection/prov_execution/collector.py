# Copyright (c) 2016 Universidade Federal Fluminense (UFF)
# Copyright (c) 2016 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""Execution provenance collector"""

import weakref

from datetime import datetime, timedelta
from ...persistence.models import Trial


class Collector(object):
    """Collector called by the transformed AST. __noworkflow__ object"""

    def __init__(self, metascript):
        self.metascript = weakref.proxy(metascript)

        # Partial save
        self.partial_save_frequency = None
        if metascript.save_frequency:
            self.partial_save_frequency = timedelta(
                milliseconds=metascript.save_frequency
            )
        self.last_partial_save = datetime.now()

    def time(self):
        """Return time at this moment
        Also check whether or not it should invoke time related methods
        """
        # ToDo #76: Processor load. Should be collected from time to time
        #                         (there are static and dynamic metadata)
        # print os.getloadavg()
        now = datetime.now()
        if (self.partial_save_frequency and
                (now - self.last_partial_save > self.partial_save_frequency)):
            self.store(partial=True)

        return now

    def store(self, partial, status="running"):
        """Store execution provenance"""
        metascript = self.metascript
        tid = metascript.trial_id

        metascript.evaluations_store.fast_store(tid, partial=partial)
        metascript.activations_store.fast_store(tid, partial=partial)
        metascript.dependencies_store.fast_store(tid, partial=partial)
        metascript.values_store.fast_store(tid, partial=partial)
        metascript.compartments_store.fast_store(tid, partial=partial)
        metascript.file_accesses_store.fast_store(tid, partial=partial)

        now = datetime.now()
        if not partial:
            Trial.fast_update(tid, metascript.main_id, now, status)

        self.last_partial_save = now
