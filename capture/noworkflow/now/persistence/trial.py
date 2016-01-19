# Copyright (c) 2014 Universidade Federal Fluminense (UFF)
# Copyright (c) 2014 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.

from __future__ import (absolute_import, print_function,
                        division, unicode_literals)

from .provider import Provider, row_to_dict


class TrialProvider(Provider):

    def store_dependencies(self, trial_id, dependencies):
        with self.db_conn as db:
            for (name, version, path, code_hash) in dependencies:
                modules = db.execute(
                    """SELECT id
                       FROM module
                       WHERE name = ?
                         AND (version IS NULL OR version = ?)
                         AND (code_hash IS NULL OR code_hash = ?)""",
                      (name, version, code_hash)).fetchone()
                if modules:
                    (module_id,) = modules
                else:
                    module_id = db.execute(
                        """INSERT INTO module (name, version, path, code_hash)
                           VALUES (?, ?, ?, ?)""",
                        (name, version, path, code_hash)).lastrowid
                db.execute(
                    """INSERT INTO dependency (trial_id, module_id)
                       VALUES (?, ?)""",
                    (trial_id, module_id))

    def store_environment(self, trial_id, env_attrs):
        with self.db_conn as db:
            db.executemany(
                """INSERT INTO environment_attr(name, value, trial_id)
                   VALUES (?, ?, ?)""",
                ((name, env_attrs[name], trial_id) for name in env_attrs)
            )

    def load_trial_id(self, trial_ref):
        try:
            with self.db_conn as db:
              (an_id,) = db.execute(
                  """SELECT trial.id
                     FROM trial LEFT OUTER JOIN tag ON trial.id = tag.trial_id
                     WHERE trial.id = :1
                        OR tag.name = :1""", (trial_ref,)).fetchone()
        except TypeError:
            an_id = None
        return an_id
