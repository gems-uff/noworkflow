# Copyright (c) 2014 Universidade Federal Fluminense (UFF), Polytechnic Institute of New York University.
# This file is part of noWorkflow. Please, consult the license terms in the LICENSE file.

from __future__ import absolute_import

from .provider import Provider, row_to_dict


class TrialProvider(Provider):

    def select_trial_id_by_condition(self, db, sql):
        try:
            (an_id,) = db.execute(
                "select id from trial where {}".format(sql)).fetchone()
        except TypeError:
            an_id = None
        return an_id

    def last_trial_id(self, script=None, parent_required=False):
        with self.db_conn as db:
            an_id = self.select_trial_id_by_condition(
                db, "start in (select max(start) "
                              "from trial where script='{}')".format(script))
            if not parent_required and not an_id:
                an_id = self.select_trial_id_by_condition(
                    db, "start in (select max(start) "
                                  "from trial)".format(script)) 
        return an_id

    def last_trial_id_without_inheritance(self):
        with self.db_conn as db:
            an_id = self.select_trial_id_by_condition(
                db, "start in (select max(start) "
                              "from trial "
                              "where inherited_id is NULL)")
        # ToDo: better exception handling
        if not an_id:
            raise TypeError
        return an_id

    def distinct_scripts(self):
        with self.db_conn as db:
            return db.execute("select distinct script from trial")

    def inherited_id(self, an_id):
        with self.db_conn as db:
            (inherited_id,) = db.execute("select inherited_id "
                                        "from trial "
                                        "where id = ?", (an_id,)).fetchone()
        return inherited_id


    def load_trial(self, trial_id):
        return self.load('trial', id=trial_id)

    def load_dependencies(self, trial_id):
        an_id = self.inherited_id(trial_id)
        if not an_id:
            an_id = trial_id
        with self.db_conn as db:
            return db.execute('select id, name, version, path, code_hash '
                              'from module as m, dependency as d '
                              'where m.id = d.module_id '
                                'and d.trial_id = ? '
                              'order by id', (an_id,))

    def function_activation_id_seq(self):
        try:
            with self.db_conn as db:
                (an_id,) = db.execute(
                    "select seq "
                    "from SQLITE_SEQUENCE "
                    "WHERE name='function_activation'").fetchone()
        except TypeError:
            an_id = 0
        return an_id + 1

    def store_dependencies(self, trial_id, dependencies):
        with self.db_conn as db:
            for (name, version, path, code_hash) in dependencies:
                modules = db.execute(
                    'select id '
                    'from module '
                    'where name = ? '
                      'and (version is null or version = ?) '
                      'and (code_hash is null or code_hash = ?)', 
                      (name, version, code_hash)).fetchone()
                if modules:
                    (module_id,) = modules
                else:
                    module_id = db.execute(
                        "insert into module (name, version, path, code_hash) "
                        "values (?, ?, ?, ?)", 
                        (name, version, path, code_hash)).lastrowid
                db.execute(
                    "insert into dependency (trial_id, module_id) "
                    "values (?, ?)", 
                    (trial_id, module_id))

    def store_environment(self, trial_id, env_attrs):
        with self.db_conn as db:
            db.executemany(
                "insert into environment_attr(name, value, trial_id) "
                "values (?, ?, ?)", 
                ((name, env_attrs[name], trial_id) for name in env_attrs)
            )

