# Copyright (c) 2014 Universidade Federal Fluminense (UFF), Polytechnic Institute of New York University.
# This file is part of noWorkflow. Please, consult the license terms in the LICENSE file.

from __future__ import absolute_import

import os
import json

from .provider import Provider


class CheckoutProvider(Provider):

    def load_parent_id(self, script, remove=True, parent_required=False):
        an_id, parents = None, {}
        if os.path.exists(self.parent_config_path):
            with self.std_open(self.parent_config_path, 'r') as f:
                parents = json.load(f)
            if script in parents:
                an_id = parents[script]
            if remove and an_id:
                del parents[script]
                with self.std_open(self.parent_config_path, 'w') as f:
                    json.dump(parents, f)
        if not an_id:
            an_id = self.last_trial_id(script=script, 
                                      parent_required=parent_required)
        return an_id

    def store_parent(self, script, trial_id):
        parents = {}
        if os.path.exists(self.parent_config_path):
            with self.std_open(self.parent_config_path, 'r') as f:
                parents = json.load(f)
        parents[script] = trial_id
        with self.std_open(self.parent_config_path, 'w') as f:
            json.dump(parents, f)
