# Copyright (c) 2014 Universidade Federal Fluminense (UFF)
# Copyright (c) 2014 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.

from __future__ import (absolute_import, print_function,
                        division, unicode_literals)

from .provider import Provider, row_to_dict


class TrialProvider(Provider):

    def select_trial_id_by_condition(self, db, sql):
        try:
            (an_id,) = db.execute(
                "SELECT id FROM trial WHERE {}".format(sql)).fetchone()
        except TypeError:
            an_id = None
        return an_id

    def last_trial_id(self, script=None, parent_required=False):
        with self.db_conn as db:
            an_id = self.select_trial_id_by_condition(
                db, "start IN (SELECT max(start) "
                              "FROM trial WHERE script='{}')".format(script))
            if not parent_required and not an_id:
                an_id = self.select_trial_id_by_condition(
                    db, "start IN (SELECT max(start) "
                                  "FROM trial)".format(script))
        return an_id

    def last_trial_id_without_inheritance(self):
        with self.db_conn as db:
            an_id = self.select_trial_id_by_condition(
                db, "start IN (SELECT max(start) "
                              "FROM trial "
                              "WHERE inherited_id IS NULL)")
        if not an_id:
            raise TypeError
        return an_id

    def distinct_scripts(self):
        with self.db_conn as db:
            return db.execute("SELECT DISTINCT script FROM trial")

    def inherited_id(self, an_id):
        with self.db_conn as db:
            (inherited_id,) = db.execute(
                """SELECT inherited_id
                   FROM trial
                   WHERE id = ?""", (an_id,)).fetchone()
        return inherited_id


    def load_trial(self, trial_id):
        return self.load('trial', id=trial_id)

    def load_dependencies(self, trial_id):
        an_id = self.inherited_id(trial_id)
        if not an_id:
            an_id = trial_id
        with self.db_conn as db:
            return db.execute(
                """SELECT id, name, version, path, code_hash
                   FROM module AS m, dependency AS d
                   WHERE m.id = d.module_id
                     AND d.trial_id = ?
                   ORDER BY id""", (an_id,))

    def function_activation_id_seq(self):
        try:
            with self.db_conn as db:
                (an_id,) = db.execute(
                    """SELECT seq
                       FROM SQLITE_SEQUENCE
                       WHERE name='function_activation'""").fetchone()
        except TypeError:
            an_id = 0
        return an_id + 1

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
