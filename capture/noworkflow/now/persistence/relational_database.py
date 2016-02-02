# Copyright (c) 2016 Universidade Federal Fluminense (UFF)
# Copyright (c) 2016 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""Relational Database"""
from __future__ import (absolute_import, print_function,
                        division, unicode_literals)

import threading

from os.path import join, exists

from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import scoped_session, sessionmaker

from ..utils.io import print_msg


DB_FILENAME = "db.sqlite"


class RelationalDatabase(object):
    """Relational Database deal with SQLite connection"""

    def __init__(self, persistence_config):
        self.db_path = None  # Database path
        self.engine = None
        self._session_map = {}
        self.session_factory = sessionmaker()

        self.base = declarative_base()

        persistence_config.add(self)

    def set_path(self, config):
        """Set content_path"""
        self.db_path = join(config.provenance_path, DB_FILENAME)

    def mock(self, config):                                                      # pylint: disable=unused-argument
        """Mock path for tests"""
        self.db_path = ""

    def connect(self, config):
        """Create database connection
        If database does not exist, create it as well
        """
        new_db = not exists(self.db_path)

        if config.should_mock:
            new_db, self.db_path = True, ""

        self.engine = create_engine(
            "sqlite://" + ("/" if self.db_path else "") + self.db_path,
            echo=False)
        self.session_factory.configure(bind=self.engine, autoflush=False,
                                       expire_on_commit=True)
        self._session_map = {}

        if new_db:
            print_msg("creating provenance database")
            self.base.metadata.create_all(self.engine)

    def make_session(self):
        """Create thread safe session"""
        return scoped_session(self.session_factory)

    @property
    def session(self):
        """Access session of current thread"""
        ident = threading.current_thread().ident
        if ident not in self._session_map:
            self._session_map[ident] = self.make_session()
            self._session_map[ident].configure(expire_on_commit=False)
        return self._session_map[ident]

    def query(self, text):
        """Perform SQL query"""
        return self.session.execute(text).fetchall()
