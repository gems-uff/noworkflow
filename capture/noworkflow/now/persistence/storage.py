# Copyright (c) 2014 Universidade Federal Fluminense (UFF)
# Copyright (c) 2014 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.

from __future__ import (absolute_import, print_function,
                        division, unicode_literals)

import hashlib
import os

from .provider import Provider


class StorageProvider(Provider):

    def put(self, content):
        content_hash = hashlib.sha1(content).hexdigest()
        content_dirname = os.path.join(self.content_path, content_hash[:2])
        if not os.path.isdir(content_dirname):
            os.makedirs(content_dirname)
        content_filename = os.path.join(content_dirname, content_hash[2:])
        if not os.path.isfile(content_filename):
            with self.std_open(content_filename, "wb") as content_file:
                content_file.write(content)
        return content_hash

    def get(self, content_hash):
        content_filename = os.path.join(self.content_path,
                                        content_hash[:2],
                                        content_hash[2:])
        with self.std_open(content_filename, 'rb') as content_file:
            return content_file.read()
