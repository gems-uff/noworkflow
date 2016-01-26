# Copyright (c) 2015 Universidade Federal Fluminense (UFF)
# Copyright (c) 2015 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
""" Persistence functions to collect provenance from 'now run' """
from __future__ import (absolute_import, print_function,
                        division, unicode_literals)

from itertools import chain
from datetime import datetime

from ..cross_version import items, lmap

from .provider import Provider


class RunProvider(Provider):
    """ Subclass of Persistence Provider
        Store <run> provenance """

    def store_trial(self, start, script, code, arguments, bypass_modules,
                    command, run=True):
        """ Store basic Trial data """
        from ..models import Trial
        code_hash = self.put(code)

        # ToDo: use core query
        parent = Trial.load_parent(script, parent_required=True)
        parent_id = parent.id if parent else None

        inherited_id = None
        if bypass_modules:
            inherited_id = Trial.fast_last_trial_id_without_inheritance()
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
