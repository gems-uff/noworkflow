# Copyright (c) 2015 Universidade Federal Fluminense (UFF)
# Copyright (c) 2015 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
""" Persistence functions to collect provenance from 'now run' """
from __future__ import (absolute_import, print_function,
                        division, unicode_literals)

from itertools import chain
from datetime import datetime
from .provider import Provider
from ..cross_version import items, lmap


def partial_save(is_complete, result_tuple):
    """ Iterate at ObjectStore and remove objects if <partial> """
    def generator(object_store, partial):
        """ Generator """
        for a in (v for k, v in items(object_store) if v):
            if partial and is_complete(a):
                del object_store[a.id]
            yield result_tuple(a)
        if partial:
            object_store.clear()
    return generator


class RunProvider(Provider):
    """ Subclass of Persistence Provider
        Store <run> provenance """

    def store_trial(self, start, script, code, arguments, bypass_modules,
                    command, run=True):
        """ Store basic Trial data """
        code_hash = self.put(code)
        parent_id = self.load_parent_id(script, parent_required=True)
        inherited_id = None
        if bypass_modules:
            inherited_id = self.last_trial_id_without_inheritance()
        with self.db_conn as db:
            trial_id = db.execute(
                """INSERT INTO trial (start, script, code_hash, arguments,
                                      command, inherited_id, parent_id, run)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (start, script, code_hash, arguments,
                      command, inherited_id, parent_id, run)).lastrowid
        return trial_id

    def update_trial(self, trial_id, finish, partial):
        """ Update basic Trial data """
        with self.db_conn as db:
            db.execute(
                """UPDATE trial
                   SET finish = ?
                   WHERE id = ?""", (finish, trial_id))

    def find_tag(self, trial_id, code_hash, command):
        query = """SELECT Tag.name
                   FROM tag Tag, trial Trial
                   WHERE Trial.id <> :1
                     AND Tag.trial_id = Trial.id
                     AND type = 'AUTO'
                """
        conditions = [
            (1, """AND Trial.code_hash = :2
                   AND Trial.command = :3""", [code_hash, command]),
            (2, """AND Trial.code_hash = :2""", [code_hash]),
            (3, "", [])
        ]

        for typ, condition, args in conditions:
            with self.db_conn as db:
                results = db.execute(query + condition,
                                     [trial_id] + args)
                tags = [lmap(int, tag[0].split('.')) for tag in results]
                if tags:
                    return typ, max(tags)

        return 0, [1, 1, 1]

    def auto_tag(self, trial_id, code, command):
        code_hash = self.put(code)
        tag_typ, tag = self.find_tag(trial_id, code_hash, command)
        new_tag = ''
        if tag_typ == 1:
            tag[2] += 1
        elif tag_typ == 2:
            tag[1] += 1
            tag[2] = 1
        elif tag_typ == 3:
            tag[0] += 1
            tag[1] = 1
            tag[2] = 1
        new_tag = '.'.join(map(str, tag))
        with self.db_conn as db:
            db.execute(
                """INSERT INTO tag(trial_id, type, name, timestamp)
                   VALUES (?, ?, ?, ?)""",
                (trial_id, 'AUTO', new_tag, datetime.now())
            )

    def store_objects(self, objects, obj_type, function_def_id):
        """ Store Function Definition objects (param, global, call) """
        with self.db_conn as db:
            db.executemany(
                """INSERT INTO object(name, type, function_def_id)
                   VALUES (?, ?, ?)""",
                ((name, obj_type, function_def_id) for name in objects)
            )

    def store_function_defs(self, trial_id, functions):
        """ Store Function Definitions """
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

    def store_activations(self, trial_id, activations, partial):
        """ Store Function Activations """
        generator = partial_save((lambda a: a.finish != 0.0), (lambda a: (
            trial_id, a.id, a.name, a.line, a.return_value, a.start, a.finish,
            a.caller_id)))
        with self.db_conn as db:
            db.executemany(
                """REPLACE INTO function_activation(
                    trial_id, id, name, line, return, start, finish, caller_id)
                VALUES (:0, :1, :2, :3, :4, :5, :6, :7)""",
                generator(activations, partial)
            )

    def store_object_values(self, trial_id, object_values, partial):
        """ Store Function Activation object values (arg, global) """
        generator = partial_save((lambda o: True), (lambda o: (
            trial_id, o.id, o.function_activation_id, o.name, o.value,
            o.type)))
        with self.db_conn as db:
            db.executemany(
                """REPLACE INTO object_value(
                    trial_id, id, function_activation_id, name, value, type)
                VALUES (:0, :1, :2, :3, :4, :5)""",
                generator(object_values, partial)
            )

    def store_file_accesses(self, trial_id, file_accesses, partial):
        """ Store File Accesses """
        generator = partial_save((lambda f: f.done), (lambda f: (
            trial_id, f.id, f.name, f.mode, f.buffering, f.timestamp,
            f.function_activation_id,f.content_hash_before,
            f.content_hash_after)))
        with self.db_conn as db:
            db.executemany(
                 """REPLACE INTO file_access(trial_id, id, name, mode,
                    buffering, timestamp, function_activation_id,
                    content_hash_before, content_hash_after)
                VALUES (:0, :1, :2, :3, :4, :5, :6, :7, :8)""",
                generator(file_accesses, partial)
            )

    def store_slicing_variables(self, trial_id, variables, partial):
        """ Store Slicing Variables """
        generator = partial_save((lambda v: False), (lambda v: (
            trial_id, v.id, v.activation_id, v.name, v.line, v.value, v.time)))
        with self.db_conn as db:
            db.executemany(
                 """REPLACE INTO slicing_variable(trial_id, id, activation_id,
                    name, line, value, time)
                VALUES (:0, :1, :2, :3, :4, :5, :6)""",
                generator(variables, partial)
            )

    def store_slicing_dependencies(self, trial_id, dependencies, partial):
        """ Store Slicing Dependencies """
        generator = partial_save((lambda d: True), (lambda d: (
            trial_id, d.id, d.dependent_activation, d.dependent,
            d.supplier_activation, d.supplier)))
        with self.db_conn as db:
            db.executemany(
                 """REPLACE INTO slicing_dependency(trial_id, id,
                    dependent_activation_id, dependent,
                    supplier_activation_id, supplier)
                VALUES (:0, :1, :2, :3, :4, :5)""",
                generator(dependencies, partial)
            )

    def store_slicing_usages(self, trial_id, usages, partial):
        """ Store Slicing Usages """
        generator = partial_save((lambda u: True), (lambda u: (
            trial_id, u.id, u.activation_id, u.variable_id, u.name, u.line, u.ctx)))
        with self.db_conn as db:
            db.executemany(
                 """REPLACE INTO slicing_usage(trial_id, id, activation_id,
                    variable_id, name, line, context)
                VALUES (:0, :1, :2, :3, :4, :5, :6)""",
                generator(usages, partial)
            )
