# Copyright (c) 2019 Universidade Federal Fluminense (UFF)
# Copyright (c) 2019 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""GitDb content database engine"""
import hashlib
from io import BytesIO

from gitdb import IStream, LooseObjectDB

from .pygit_engine import PyGitEngine

# ToDo: implement other methods using GitDB to not depend on PyGitEngine

class GitDBPyGitEngine(PyGitEngine):

    @staticmethod
    def do_put(content_path, object_hashes, content, filename):
        """Perform put operation. This is used in the distributed wrapper"""
        ldb = LooseObjectDB("/{}/objects/".format(content_path))
        istream = IStream("blob", len(content), BytesIO(content))
        ldb.store(istream)
        content_hash = istream.hexsha
        # Names the file's entry in the content commit; nothing is verified with it
        filename_hash = hashlib.sha1(
            filename.encode('utf-8'), usedforsecurity=False).hexdigest()
        result = object_hashes[filename_hash] = str(content_hash.decode('utf-8'))
        return result
