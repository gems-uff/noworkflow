# Copyright (c) 2014 Universidade Federal Fluminense (UFF)
# Copyright (c) 2014 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.

from __future__ import (absolute_import, print_function,
                        division, unicode_literals)

from .provider import Provider


class DatabaseProvider(Provider):

    def load(self, table_name, selection=["*"], order="id", **condition):
        where = '1'
        for key in condition:
            if condition[key] is None:
                where += ' and {} is NULL'.format(key)
            else:
                where += ' and {} = {}'.format(key, condition[key])

        with self.db_conn as db:
            return db.execute('SELECT {} FROM {} WHERE {} ORDER BY {}'.format(
                ','.join(selection), table_name, where, order))

    def insert(self, table_name, attrs, **extra_attrs):
        # Not in use, but can be useful in the future
        query = 'INSERT INTO {}({}) VALUES ({})'.format(
            table_name,
            ','.join(attrs.keys() + extra_attrs.keys()),
            ','.join(['?'] * (len(attrs) + len(extra_attrs)))
        )
        with self.db_conn as db:
            db.execute(query, attrs.values() + extra_attrs.values())

    def insertmany(self, table_name, attrs_list, **extra_attrs):
        # Not in use, but can be useful in the future
        for attrs in attrs_list:
            self.insert(table_name, attrs, **extra_attrs)
