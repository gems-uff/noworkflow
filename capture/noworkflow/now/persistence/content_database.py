# Copyright (c) 2016 Universidade Federal Fluminense (UFF)
# Copyright (c) 2016 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""Content Database"""
from __future__ import (absolute_import, print_function,
                        division, unicode_literals)

import hashlib
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

    def mock(self, config):                                                      # pylint: disable=unused-argument, no-self-use
        """Mock storage for tests"""
        ContentDatabase.put = lambda s, c: hashlib.sha1(c).hexdigest()
        ContentDatabase.get = lambda s, c: "".encode("utf-8")

    def connect(self, config):
        """Create content directory"""
        if not config.should_mock and not isdir(self.content_path):
            os.makedirs(self.content_path)

    def put(self, content):
        """Put content in the content database

        Return: content hash code

        Arguments:
        content -- binary text to be saved
        """
        content_hash = hashlib.sha1(content).hexdigest()
        content_dirname = join(self.content_path, content_hash[:2])
        if not isdir(content_dirname):
            os.makedirs(content_dirname)
        content_filename = join(content_dirname, content_hash[2:])
        if not isfile(content_filename):
            with self.std_open(content_filename, "wb") as content_file:
                content_file.write(content)
        return content_hash

    def find_subhash(self, content_hash):
        """Get hash that starts by content_hash"""
        content_dirname = content_hash[:2]
        contet_filename = content_hash[2:]
        content_dir = join(self.content_path, content_dirname)
        if not isdir(content_dir):
            return None
        for _, _, filenames in os.walk(content_dir):
            for name in filenames:
                if name.startswith(contet_filename):
                    return content_dirname + name
        return None


    def get(self, content_hash):
        """Get content from the content database

        Return: content

        Arguments:
        content_hash -- content hash code
        """
        content_filename = join(self.content_path,
                                content_hash[:2],
                                content_hash[2:])
        with self.std_open(content_filename, "rb") as content_file:
            return content_file.read()
