# Copyright (c) 2014 Universidade Federal Fluminense (UFF)
# Copyright (c) 2014 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.

from __future__ import (absolute_import, print_function,
                        division, unicode_literals)

import os
import json

from .provider import Provider, row_to_dict


class CheckoutProvider(Provider):

    def remove_head(self, trial_id):
        with self.db_conn as db:
            db.execute('''DELETE FROM head
                          WHERE trial_id=?''', (trial_id,))

    def load_head(self, script):
        try:
            with self.db_conn as db:
                (an_id,) = db.execute(
                    '''SELECT trial_id
                       FROM head
                       WHERE script=?''', (script,)).fetchone()
                return an_id
        except TypeError:
            return None

    def load_parent_id(self, script, remove=True, parent_required=False):
        an_id = self.load_head(script)
        if an_id and remove:
            self.remove_head(an_id)
        elif not an_id:
            an_id = self.last_trial_id(script=script,
                                       parent_required=parent_required)
        return an_id

    def store_parent(self, script, trial_id):
        an_id = self.load_head(script)
        with self.db_conn as db:
            if an_id:
                db.execute('''UPDATE head
                              SET trial_id=?
                              WHERE script=?''', (trial_id, script))
            else:
                db.execute("""INSERT INTO head(trial_id, script)
                              VALUES(?,?)""", [trial_id, script])
