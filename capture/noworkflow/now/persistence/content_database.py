# Copyright (c) 2016 Universidade Federal Fluminense (UFF)
# Copyright (c) 2016 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""Content Database"""
from __future__ import (absolute_import, print_function,
                        division, unicode_literals)

import os

from os.path import join, isdir, isfile


CONTENT_DIRNAME = "content"


class ContentDatabase(object):
    """Content Database deal with storage of file content in disk"""

    def __init__(self, persistence_config):
        self.content_path = None  # Base path for storing content of files
        self.std_open = open  # Original Python open function.
        persistence_config.add(self)

    def set_path(self, config):
        """Set content_path"""
        self.content_path = join(config.provenance_path, CONTENT_DIRNAME)

    def commit_content(self, message):
        pass

    def gc(self):
        pass