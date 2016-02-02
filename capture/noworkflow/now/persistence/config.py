# Copyright (c) 2016 Universidade Federal Fluminense (UFF)
# Copyright (c) 2016 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""General persistence Configurations"""
from __future__ import (absolute_import, print_function,
                        division, unicode_literals)

import sys

from os.path import join, isdir

from ..utils.io import print_msg


PROVENANCE_DIRNAME = ".noworkflow"


class PersistenceConfig(object):
    """Config persistence. Interface for connecting to directory"""

    def __init__(self, path=None, connect=False):
        self.base_path = None  # Exeution path
        self.provenance_path = None  # Base .noworkflow path
        self.db_conn = None  # Connection to the database
        self.should_mock = False

        if path:
            self.path = path

        if connect:
            self.connect(path)

        self.delegate = []

    @property
    def path(self):
        """Return database path"""
        return self.base_path

    @path.setter
    def path(self, path):
        self.base_path = path
        self.provenance_path = join(path, PROVENANCE_DIRNAME)

        for obj in self.delegate:
            obj.set_path(self)

    def _has_provenance(self, path=None):
        """Check if persistence path exists"""
        if path:
            return isdir(join(path, PROVENANCE_DIRNAME))
        return isdir(self.provenance_path)

    def mock(self):
        """Mock database access"""
        self.should_mock = True
        for obj in self.delegate:
            obj.mock(self)

    def connect(self, path=None):
        """Connect to persistence"""
        if path:
            self.path = path

        for obj in self.delegate:
            obj.connect(self)

    def connect_existing(self, path=None):
        """Connect to existing persistence. Exit if it does not exist."""
        if path:
            self.path = path
        if not self._has_provenance():
            print_msg("there is no provenance store in the current directory",
                      True)
            sys.exit(1)
        self.connect()

    def add(self, obj):
        """Add database manager to config for delegation"""
        self.delegate.append(obj)
