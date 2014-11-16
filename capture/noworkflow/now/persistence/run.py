# Copyright (c) 2014 Universidade Federal Fluminense (UFF), Polytechnic Institute of New York University.
# This file is part of noWorkflow. Please, consult the license terms in the LICENSE file.

from __future__ import absolute_import

from .provider import Provider

class RunProvider(Provider):

    def store_trial(self, start, script, code, arguments, bypass_modules, run=True):
        code_hash = self.put(code.encode('utf-8'))
        parent_id = self.load_parent_id(script, parent_required=True)
        inherited_id = self.last_trial_id_without_inheritance() if bypass_modules else None
        with self.db_conn as db:
            trial_id = db.execute(
                "insert into trial (start, script, code_hash, arguments, "
                    "inherited_id, parent_id, run) "
                "values (?, ?, ?, ?, ?, ?, ?)", 
                (start, script, code_hash, arguments, 
                    inherited_id, parent_id, run)).lastrowid
        return trial_id

    def update_trial(self, trial_id, finish, function_activation):
        self.store_function_activation(trial_id, function_activation, None)
        with self.db_conn as db:
            db.execute("update trial "
                       "set finish = ? "
                       "where id = ?", (finish, trial_id))

    def store_objects(self, objects, obj_type, function_def_id):
        with self.db_conn as db:
            db.executemany(
                "insert into object(name, type, function_def_id) "
                "values (?, ?, ?)",
                ((name, obj_type, function_def_id) for name in objects)
            )

    def store_function_defs(self, trial_id, functions):
        with self.db_conn as db:
            for name, defs in functions.items():
                arguments, global_vars, calls, code_hash = defs
                function_def_id = db.execute(
                    "insert into function_def(name, code_hash, trial_id) "
                    "values (?, ?, ?)", 
                    (name, code_hash, trial_id)).lastrowid
                self.store_objects(arguments, 'ARGUMENT', function_def_id)
                self.store_objects(global_vars, 'GLOBAL', function_def_id)
                self.store_objects(calls, 'FUNCTION_CALL', function_def_id)

    def extract_function_activation(self, trial_id, activation, caller_id, activation_id):
        return (
            activation_id, activation.name, activation.line,
            activation.return_value, activation.start, activation.finish,
            caller_id, trial_id,
        )

    def extract_object_values(self, object_values, obj_type, function_activation_id):
        for name in object_values:
            yield (name, object_values[name], obj_type, function_activation_id)

    def extract_file_accesses(self, trial_id, file_accesses, function_activation_id):
        for file_access in file_accesses:
            yield (
                file_access['name'],
                file_access['mode'],
                file_access['buffering'],
                file_access['content_hash_before'],
                file_access['content_hash_after'],
                file_access['timestamp'],
                function_activation_id,
                trial_id
            )

    def store_function_activation(self, trial_id, function_activation, caller_id):
        function_activations, object_values, file_accesses = [], [], []
        d = { 
            'fid': self.function_activation_id_seq(),
            'activations': function_activations,
            'object_values': object_values,
            'file_accesses': file_accesses,
        }

        def add_activation(trial_id, function_activation, caller_id):
            fid = d['fid']
            d['activations'].append(
                self.extract_function_activation(trial_id, function_activation, caller_id, fid)
            )
            for object_value in self.extract_object_values(function_activation.arguments, 'ARGUMENT', fid):
                d['object_values'].append(object_value)

            for object_value in self.extract_object_values(function_activation.globals, 'GLOBAL', fid):
                d['object_values'].append(object_value)

            for file_access in self.extract_file_accesses(trial_id, function_activation.file_accesses, fid):
                d['file_accesses'].append(file_access)

            d['fid'] += 1
            
            for inner_function_activation in function_activation.function_activations:
                add_activation(trial_id, inner_function_activation, fid)

        add_activation(trial_id, function_activation, caller_id)


        with self.db_conn as db:
            db.executemany(
                "insert into function_activation(id, name, line, return, "
                    "start, finish, caller_id, trial_id) "
                "values (?, ?, ?, ?, ?, ?, ?, ?)",
                function_activations
            )
            db.executemany(
                "insert into object_value(name, value, type, "
                    "function_activation_id) "
                "values (?, ?, ?, ?)",
                object_values
            )
            db.executemany(
                "insert into file_access(name, mode, buffering, "
                    "content_hash_before, content_hash_after, timestamp, "
                    "function_activation_id, trial_id) "
                "values (?, ?, ?, ?, ?, ?, ?, ?)",
                file_accesses
            )

    def store_slicing(self, trial_id, variables, dependencies, usages):
        with self.db_conn as db:
            db.executemany(
                "insert into slicing_variable(trial_id, vid, name, "
                    "line, value, time) "
                "values (?, ?, ?, ?, ?, ?)",
                ((trial_id, v.id, v.name, v.line, v.value, v.time) for v in variables)
            )
            db.executemany(
                "insert into slicing_dependency(trial_id, id, "
                    "dependent, supplier) "
                "values (?, ?, ?, ?)",
                ((trial_id, d.id, d.dependent, d.supplier) for d in dependencies)
            )
            db.executemany(
                "insert into slicing_usage(trial_id, id, vid, "
                    "name, line) "
                "values (?, ?, ?, ?, ?)",
                ((trial_id, u.id, u.vid, u.name, u.line) for u in usages)
            )