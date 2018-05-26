# Copyright (c) 2016 Universidade Federal Fluminense (UFF)
# Copyright (c) 2016 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""Content Database"""
from __future__ import (absolute_import, print_function,
                        division, unicode_literals)

from os.path import join, isdir, isfile
from ..persistence.content_database_engine import PyGitContentDatabaseEngine, StandardContentDatabaseEngine


STANDARD_DATABASE_DIR = 'content'
GIT_DATABASE_DIR = 'content.git'

class ContentDatabase(object):
    """Content Database deal with storage of file content in disk"""

    def __init__(self, persistence_config):
        self.content_path = None  # Base path for storing content of files
        persistence_config.add(self)
        self.content_database_engine = None

    def set_path(self, config):
        """Set content_path"""

        if not isdir(join(config.provenance_path, STANDARD_DATABASE_DIR)):
            """Standard content database found"""
            config.content_dir = STANDARD_DATABASE_DIR
            self.content_path = join(config.provenance_path, config.content_dir)
        else:
            """if not use git content database"""
            config.content_dir = GIT_DATABASE_DIR
            self.content_path = join(config.provenance_path, config.content_dir)

    def connect(self, config):
        if config.content_dir == GIT_DATABASE_DIR:
            self.content_database_engine = PyGitContentDatabaseEngine(self.content_path)
        else:
            self.content_database_engine = StandardContentDatabaseEngine(self.content_path)

        self.content_database_engine.connect()

    def commit_content(self, message):
        if isinstance(self.content_database_engine, PyGitContentDatabaseEngine):
            self.content_database_engine.commit_content(message)

    def mock(self, config):
        pass

    def find_subhash(self, content_hash):
        return None

    def gc(self):
        if isinstance(self.content_database_engine, PyGitContentDatabaseEngine):
            self.content_database_engine.gc()

    def put(self, content):
        print('putting content')
        return self.content_database_engine.put(content)

    def get(self, content_hash):
        return self.content_database_engine.get(content_hash)