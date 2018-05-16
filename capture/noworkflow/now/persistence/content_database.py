# Copyright (c) 2016 Universidade Federal Fluminense (UFF)
# Copyright (c) 2016 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""Content Database"""
from __future__ import (absolute_import, print_function,
                        division, unicode_literals)

import os
import hashlib

from os.path import join, isdir, isfile


class ContentDatabase(object):
    """Content Database deal with storage of file content in disk"""

    def __init__(self, persistence_config):
        self.content_path = None  # Base path for storing content of files
        self.std_open = open  # Original Python open function.
        persistence_config.add(self)

    def set_path(self, config):
        """Set content_path"""
        self.content_path = join(config.provenance_path, config.content_dir)

    def commit_content(self, message):
        pass

    def mock(self, config):
        pass

    def find_subhash(self, content_hash):
        return None

    def gc(self):
        pass

    def put(self, content):
        pass

    def get(self, content_hash):
        pass

    def join_persistence_threads(self):
        pass

    def get_hash_from_content(self, content):
        git_content = b'blob ' + str(len(content)) + b'\0'
        hash = hashlib.sha1(git_content + content).hexdigest()
        return hash
