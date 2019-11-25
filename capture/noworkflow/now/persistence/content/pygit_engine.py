# Copyright (c) 2019 Universidade Federal Fluminense (UFF)
# Copyright (c) 2019 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""PyGit content database engine"""
import hashlib

from os.path import isdir

from pygit2 import init_repository
from pygit2 import Repository
from pygit2 import GIT_FILEMODE_BLOB
from pygit2 import Signature

from .gitbase import GitContentDatabaseEngine
from .parallel import create_distributed, create_pool, create_threading


class PyGitEngine(GitContentDatabaseEngine):
    def __init__(self, config):
        super(PyGitEngine, self).__init__(config)
        self.object_hashes = {}
        self.repo = None
        self.tree_builder = None
    
    def _create_initial_commit(self):
        """Create the initial commit of the git repository"""
        empty_tree = self.tree_builder.write()
        self._create_commit_object(self._initial_message, empty_tree)

    def _create_commit_object(self, message, tree):
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

    def connect(self):
        """Create content directory"""
        
        if not isdir(self.content_path):
            init_repository(self.content_path, bare=True)
            self.repo = Repository(self.content_path)
            self.tree_builder = self.repo.TreeBuilder()
            self._create_initial_commit()
        else:
            self.repo = Repository(self.content_path)
            self.tree_builder = self.repo.TreeBuilder()
        
    @staticmethod
    def do_put(content_path, object_hashes, content, filename):
        """Perform put operation. This is used in the distributed wrapper"""
        content_hash = Repository(content_path).create_blob(content)
        filename_hash = hashlib.sha1(filename.encode('utf-8')).hexdigest()
        result = object_hashes[filename_hash] = str(content_hash)
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
    
    def commit_content(self, message):
        """Commit the current files of content database"""
        self.close()
        for key, value in self.object_hashes.items():
            self.tree_builder.insert(key, value, GIT_FILEMODE_BLOB)

        commit_oid = self._create_commit_object(
            message, self.tree_builder.write()
        )

        return commit_oid

    def find_subhash(self, content_hash):
        """Find hash in git"""
        try:
            blob = self.repo.revparse_single(content_hash)
            return str(blob.id)
        except KeyError:
            return None


DistributedPyGitEngine = create_distributed(PyGitEngine)
PoolPyGitEngine = create_pool(PyGitEngine)
ThreadingPyGitEngine = create_threading(PyGitEngine)
