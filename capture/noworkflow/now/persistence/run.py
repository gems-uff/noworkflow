# Copyright (c) 2014 Universidade Federal Fluminense (UFF)
# Copyright (c) 2014 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.

from __future__ import (absolute_import, print_function,
                        division, unicode_literals)

from .provider import Provider

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

    def update_trial(self, trial_id, finish, function_activation):
        self.store_function_activation(trial_id, function_activation, None)
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
            for name, defs in functions.items():
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

    def extract_object_values(self, object_values, obj_type, activation_id):
        for name in object_values:
            yield (name, object_values[name], obj_type, activation_id)

    def extract_file_accesses(self, trial_id, file_accesses, activation_id):
        for file_access in file_accesses:
            yield (
                file_access['name'],
                file_access['mode'],
                file_access['buffering'],
                file_access['content_hash_before'],
                file_access['content_hash_after'],
                file_access['timestamp'],
                activation_id,
                trial_id
            )

    def store_function_activation(self, trial_id, activation, caller_id):
        function_activations, object_values, file_accesses = [], [], []
        d = {
            'fid': self.function_activation_id_seq(),
            'activations': function_activations,
            'object_values': object_values,
            'file_accesses': file_accesses,
        }

        def add_activation(trial_id, act, caller_id):
            fid = d['fid']
            d['activations'].append(
                self.extract_function_activation(trial_id, act, caller_id, fid)
            )
            for object_value in self.extract_object_values(act.arguments,
                                                           'ARGUMENT', fid):
                d['object_values'].append(object_value)

            for object_value in self.extract_object_values(act.globals,
                                                           'GLOBAL', fid):
                d['object_values'].append(object_value)

            for file_access in self.extract_file_accesses(trial_id,
                                                          act.file_accesses,
                                                          fid):
                d['file_accesses'].append(file_access)

            d['fid'] += 1

            for inner_function_activation in act.function_activations:
                add_activation(trial_id, inner_function_activation, fid)

        add_activation(trial_id, activation, caller_id)


        with self.db_conn as db:
            db.executemany(
                """INSERT INTO function_activation(id, name, line, return,
                    start, finish, caller_id, trial_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                function_activations
            )
            db.executemany(
                """INSERT INTO object_value(name, value, type,
                    function_activation_id)
                VALUES (?, ?, ?, ?)""",
                object_values
            )
            db.executemany(
                """INSERT INTO file_access(name, mode, buffering,
                    content_hash_before, content_hash_after, timestamp,
                    function_activation_id, trial_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                file_accesses
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
                """INSERT INTO slicing_usage(trial_id, id, vid, name, line)
                VALUES (?, ?, ?, ?, ?)""",
                ((trial_id, u.id, u.vid, u.name, u.line) for u in usages)
            )
