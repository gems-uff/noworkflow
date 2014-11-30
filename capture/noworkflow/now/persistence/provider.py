# Copyright (c) 2014 Universidade Federal Fluminense (UFF)
# Copyright (c) 2014 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.

from __future__ import (absolute_import, print_function,
                        division, unicode_literals)

import sqlite3

from os.path import join, isdir, exists
from os import makedirs
from pkg_resources import resource_string

from ..utils import print_msg


PROVENANCE_DIRNAME = '.noworkflow'
CONTENT_DIRNAME = 'content'
DB_FILENAME = 'db.sqlite'
DB_SCRIPT = '../../resources/noworkflow.sql'
PARENT_TRIAL = '.parent_config.json'


def row_to_dict(row):
    return dict(zip(row.keys(), row))


class Provider(object):

    def __init__(self, path=None, connect=False):
        self.base_path = None # Exeution path
        self.provenance_path = None  # Base .noworflow path
        self.content_path = None # Base path for storing content of files
        self.parent_config_path = None # Base path for checkout references
        self.db_conn = None # Connection to the database

        self.std_open = open # Original Python open function.

        if path:
            self.path = path

        if connect:
            self.connect(path)

    @property
    def path(self):
        return self.base_path

    @path.setter
    def path(self, path):
        self.base_path = path
        self.provenance_path = join(path, PROVENANCE_DIRNAME)
        self.content_path = join(self.provenance_path, CONTENT_DIRNAME)
        self.parent_config_path = join(self.provenance_path, PARENT_TRIAL)

    def connect(self, path=None):
        if path:
            self.path = path

        db_path = join(self.provenance_path, DB_FILENAME)

        if not isdir(self.content_path):
            makedirs(self.content_path)

        new_db = not exists(db_path)
        self.db_conn = sqlite3.connect(db_path)
        self.db_conn.row_factory = sqlite3.Row

        if new_db:
            print_msg('creating provenance database')
            # Accessing the content of a file via setuptools
            with self.db_conn as db:
                db.executescript(resource_string(__name__, DB_SCRIPT))

    def has_provenance(self, path=None):
        if path:
            return isdir(join(path, PROVENANCE_DIRNAME))
        return isdir(self.provenance_path)

    def connect_existing(self, path=None):
        if path:
            self.path = path
        if not self.has_provenance():
            print_msg('there is no provenance store in the current directory',
                True)
            sys.exit(1)
        self.connect()
