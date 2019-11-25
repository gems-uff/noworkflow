# Copyright (c) 2019 Universidade Federal Fluminense (UFF)
# Copyright (c) 2019 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""PyGit content database engine"""
import hashlib
import os

from os.path import isdir
from collections import defaultdict

from pygit2 import init_repository
from pygit2 import Repository
from pygit2 import GIT_FILEMODE_BLOB, GIT_FILEMODE_TREE
from pygit2 import Signature

from .gitbase import GitContentDatabaseEngine
from .parallel import create_distributed, create_pool, create_threading


class PyGitEngine(GitContentDatabaseEngine):
    def __init__(self, config):
        super(PyGitEngine, self).__init__(config)
        self.repo = None
    
    def connect(self):
        """Create content directory"""
        if not isdir(self.content_path):
            init_repository(self.content_path, bare=True)
            self.repo = Repository(self.content_path)
            self.create_initial_commit()
        else:
            self.repo = Repository(self.content_path)
        
    @staticmethod
    def do_put(content_path, object_hashes, content, filename):
        """Perform put operation. This is used in the distributed wrapper"""
        content_hash = Repository(content_path).create_blob(content)
        result = object_hashes[filename] = str(content_hash)
        return result

    def put_attr(self, content, filename):
        """Return attributes for the do_put operation"""
        filename = self._inc_name(filename)
        return (
            self.content_path, self.object_hashes, content, filename
        )

    def put(self, content, filename="generic"):  # pylint: disable=method-hidden
        """Put content in the content database"""
        return self.do_put(*self.put_attr(content, filename))
    
    def get(self, content_hash):  # pylint: disable=method-hidden
        """Get content from the content database"""
        return_data = self.repo[content_hash].data
        return return_data
    
    def find_subhash(self, content_hash):
        """Find hash in git"""
        try:
            blob = self.repo.revparse_single(content_hash)
            return str(blob.id)
        except KeyError:
            return None

    def create_initial_commit(self):
        """Create the initial commit of the git repository"""
        empty_tree = self.repo.TreeBuilder().write()
        self.create_commit_object(self._initial_message, empty_tree)

    def create_commit_object(self, message, tree):
        """Create a commit object"""
        references = list(self.repo.references)

        master_ref = self.repo.lookup_reference(
            self._commit_ref
        ) if len(references) > 0 else None

        parents = []
        if master_ref is not None:
            parents = [master_ref.peel().id]

        author = Signature(self._commit_name, self._commit_email)
        return self.repo.create_commit(
            self._commit_ref, author, author, message, tree, parents
        )

    def new_tree(self, parent):
        """Create new git tree"""
        return self.repo.TreeBuilder()

    def insert_blob(self, tree, basename, value):
        """Insert blob into tree"""
        tree.insert(basename, value, GIT_FILEMODE_BLOB)

    def insert_tree(self, tree, basename, value):
        """Insert tree into tree"""
        tree.insert(basename, value, GIT_FILEMODE_TREE)

    def write_tree(self, tree):
        """Write tree to git directory"""
        return tree.write()


DistributedPyGitEngine = create_distributed(PyGitEngine)
PoolPyGitEngine = create_pool(PyGitEngine)
ThreadingPyGitEngine = create_threading(PyGitEngine)
