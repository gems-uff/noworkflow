import os
import hashlib
import time
import io

from dulwich.repo import Repo
from dulwich.objects import Tree
from dulwich.objects import Blob
from dulwich.objects import Commit
from dulwich.objects import parse_timezone
from dulwich.objectspec import scan_for_short_id

from .gitbase import GitContentDatabaseEngine
from .parallel import create_distributed, create_pool, create_threading
from . import safeopen

class DulwichEngine(GitContentDatabaseEngine):

    def __init__(self, config):
        super(DulwichEngine, self).__init__(config)
        self._commit_encoding = 'UTF-8'
        self.repo = None

    def connect(self):
        """Create content directory"""
        if not os.path.isdir(self.content_path):
            os.makedirs(self.content_path)
            Repo.init_bare(self.content_path)
            self.repo = Repo(self.content_path)
            self.create_initial_commit()
        else:
            self.repo = Repo(self.content_path)

    @staticmethod
    def do_put(content_path, object_hashes, content, filename):
        """Perform put operation. This is used in the distributed wrapper"""
        with safeopen.restore_open():
            object_store = Repo(content_path).object_store
            blob = Blob.from_string(content)
            object_store.add_object(blob)
            result = object_hashes[filename] = blob.id.decode("ascii")
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
        with self.restore_open():
            return_data = self.repo.__getitem__(
                content_hash.encode()
            ).as_pretty_string()
            return return_data

    def find_subhash(self, content_hash):
        """Find hash in git"""
        try:
            content_hash = content_hash.encode("utf-8")
            result = scan_for_short_id(self.repo.object_store, content_hash)
            if result:
                return result.id.decode("utf-8")
        except KeyError:
            return None

    def create_initial_commit(self):
        """Create the initial commit of the git repository"""
        with self.restore_open():
            object_store = self.repo.object_store
            empty_tree = Tree()
            object_store.add_object(empty_tree)
            self.create_commit_object(self._initial_message, empty_tree.id)

    def create_commit_object(self, message, tree):
        """Create a commit object"""
        with self.restore_open(): 
            master_ref = self.repo.get_refs().get(
                self._commit_ref.encode("utf-8"), None
            )
            
            commit = Commit()
            if master_ref is not None:
                commit.parents = [master_ref]

            commit.tree = tree
            author = (self._commit_name + " <" + self._commit_email + ">").encode()
            commit.author = commit.committer = author
            commit.commit_time = commit.author_time = int(time.time())
            tz = parse_timezone(time.strftime("%z").encode())[0]
            commit.commit_timezone = commit.author_timezone = tz
            commit.encoding = self._commit_encoding.encode()
            commit.message = message.encode()

            self.repo.object_store.add_object(commit)
            self.repo.refs[
                self._commit_ref.encode("utf-8")
            ] = commit.id

            return commit.id

    def new_tree(self, parent):
        """Create new git tree"""
        return Tree()

    def insert_blob(self, tree, basename, value):
        """Insert blob into tree"""
        tree.add(basename.encode('utf-8'), 0o100644, value.encode("ascii"))

    def insert_tree(self, tree, basename, value):
        """Insert tree into tree"""
        tree.add(basename.encode('utf-8'), 0o040000, value)

    def write_tree(self, tree):
        """Write tree to git directory"""
        with self.restore_open(): 
            self.repo.object_store.add_object(tree)
            return tree.id


DistributedDulwichEngine = create_distributed(DulwichEngine)
PoolDulwichEngine = create_pool(DulwichEngine)
ThreadingDulwichEngine = create_threading(DulwichEngine)
