# Copyright (c) 2014 Universidade Federal Fluminense (UFF)
# Copyright (c) 2014 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.

from __future__ import (absolute_import, print_function,
                        division, unicode_literals)

from .provider import Provider
from ..cross_version import items

class RunProvider(Provider):

    def store_trial(self, start, script, code, arguments, bypass_modules,
                    run=True):
        code_hash = self.put(code)
        parent_id = self.load_parent_id(script, parent_required=True)
        inherited_id = None
        if bypass_modules:
            inherited_id = self.last_trial_id_without_inheritance()
        with self.db_conn as db:
            trial_id = db.execute(
                """INSERT INTO trial (start, script, code_hash, arguments,
                                      inherited_id, parent_id, run)
                   VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (start, script, code_hash, arguments,
                      inherited_id, parent_id, run)).lastrowid
        return trial_id

    def update_trial(self, trial_id, finish, partial):
        if not partial:
            with self.db_conn as db:
                db.execute(
                    """UPDATE trial
                       SET finish = ?
                       WHERE id = ?""", (finish, trial_id))

    def store_objects(self, objects, obj_type, function_def_id):
        with self.db_conn as db:
            db.executemany(
                """INSERT INTO object(name, type, function_def_id)
                   VALUES (?, ?, ?)""",
                ((name, obj_type, function_def_id) for name in objects)
            )

    def store_function_defs(self, trial_id, functions):
        with self.db_conn as db:
            for name, defs in items(functions):
                arguments, global_vars, calls, code_hash = defs
                function_def_id = db.execute(
                    """INSERT INTO function_def(name, code_hash, trial_id)
                       VALUES (?, ?, ?)
                    """,(name, code_hash, trial_id)).lastrowid
                self.store_objects(arguments, 'ARGUMENT', function_def_id)
                self.store_objects(global_vars, 'GLOBAL', function_def_id)
                self.store_objects(calls, 'FUNCTION_CALL', function_def_id)

    def extract_function_activation(self, trial_id, activation, caller_id,
                                    activation_id):
        return (
            activation_id, activation.name, activation.line,
            activation.return_value, activation.start, activation.finish,
            caller_id, trial_id,
        )

    def store_activations(self, trial_id, activations):
        with self.db_conn as db:
            db.executemany(
                """INSERT INTO function_activation(trial_id, id, name, line,
                    return, start, finish, caller_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                ((trial_id, a.id, a.name, a.line,
                    a.return_value, a.start, a.finish, a.caller_id)
                    for a in activations)
            )

    def store_object_values(self, trial_id, object_values):
        with self.db_conn as db:
            db.executemany(
                """INSERT INTO object_value(trial_id, id,
                    function_activation_id, name, value, type)
                VALUES (?, ?, ?, ?, ?, ?)""",
                ((trial_id, o.id,
                    o.function_activation_id, o.name, o.value, o.type)
                    for o in object_values)
            )

    def store_file_accesses(self, trial_id, file_accesses):
        with self.db_conn as db:
            db.executemany(
                 """INSERT INTO file_access(trial_id, id, name, mode,
                    buffering, timestamp, function_activation_id,
                    content_hash_before, content_hash_after)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                ((trial_id, f.id, f.name, f.mode,
                    f.buffering, f.timestamp, f.function_activation_id,
                    f.content_hash_before, f.content_hash_after)
                    for f in file_accesses)
            )

    def store_slicing(self, trial_id, variables, dependencies, usages):
        with self.db_conn as db:
            db.executemany(
                """INSERT INTO slicing_variable(trial_id, vid, name, line,
                    value, time)
                VALUES (?, ?, ?, ?, ?, ?)""",
                ((trial_id, v.id, v.name, v.line,
                    v.value, v.time) for v in variables)
            )
            db.executemany(
                """INSERT INTO slicing_dependency(trial_id, id, dependent,
                    supplier)
                VALUES (?, ?, ?, ?)""",
                ((trial_id, d.id, d.dependent,
                    d.supplier) for d in dependencies)
            )
            db.executemany(
                """INSERT INTO slicing_usage(trial_id, id, vid, name, line,
                    context)
                VALUES (?, ?, ?, ?, ?, ?)""",
                ((trial_id, u.id, u.vid, u.name, u.line, u.ctx)
                    for u in usages)
            )
