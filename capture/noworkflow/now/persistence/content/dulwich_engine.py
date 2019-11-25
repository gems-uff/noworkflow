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
        self.object_hashes = {}
        self._commit_encoding = 'UTF-8'
        self.repo = None
        self.tree_builder = None

    def _create_initial_commit(self):
        """Create the initial commit of the git repository"""
        with self.restore_open():
            object_store = self.repo.object_store
            empty_tree = Tree()
            object_store.add_object(empty_tree)
            initial_commit = self._create_commit_object(self._initial_message, empty_tree)
            object_store.add_object(initial_commit)
            self.__set_master_ref(initial_commit.id)

    def _create_commit_object(self, message, tree, parent=None):
        """Create a commit object"""
        commit = Commit()
        if parent is not None:
            commit.parents = [parent]
        commit.tree = tree.id
        author = (self._commit_name + " <" + self._commit_email + ">").encode()
        commit.author = commit.committer = author
        commit.commit_time = commit.author_time = int(time.time())
        tz = parse_timezone(time.strftime("%z").encode())[0]
        commit.commit_timezone = commit.author_timezone = tz
        commit.encoding = self._commit_encoding.encode()
        commit.message = message.encode()
        return commit

    def connect(self):
        """Create content directory"""
        if not os.path.isdir(self.content_path):
            os.makedirs(self.content_path)
            Repo.init_bare(self.content_path)
            self.repo = Repo(self.content_path)
            self.tree_builder = Tree()
            self._create_initial_commit()
        else:
            self.repo = Repo(self.content_path)
            self.tree_builder = Tree()

    @staticmethod
    def do_put(content_path, object_hashes, content, filename):
        """Perform put operation. This is used in the distributed wrapper"""
        with safeopen.restore_open():
            filename_hash = hashlib.sha1(filename.encode('utf-8')).hexdigest()
            object_store = Repo(content_path).object_store
            blob = Blob.from_string(content)
            object_store.add_object(blob)
            result = object_hashes[filename_hash] = blob.id.decode("ascii")
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

    

    def commit_content(self, message):
        """Commit the current files of content database"""
        self.close()
        with self.restore_open():
            object_store = self.repo.object_store
            for key, value in self.object_hashes.items():
                self.tree_builder.add(key.encode('utf-8'), 0o100644, value.encode("ascii"))

            object_store.add_object(self.tree_builder)
            commit = self._create_commit_object(
                message, self.tree_builder, self.__get_master_ref()
            )
            object_store.add_object(commit)
            self.__set_master_ref(commit.id)

    

    def __get_master_ref(self):
        """Returns the master ref commit hash
        """
        return self.repo.get_refs()[
            self._commit_ref.encode("utf-8")
        ]

    def __set_master_ref(self, commit_hash):
        """Set the master ref commit
                        Arguments:
                        commit_hash -- hash of commit object
                        """
        self.repo.refs[
            self._commit_ref.encode("utf-8")
        ] = commit_hash

    def find_subhash(self, content_hash):
        """Find hash in git"""
        try:
            content_hash = content_hash.encode("utf-8")
            result = scan_for_short_id(self.repo.object_store, content_hash)
            if result:
                return result.id.decode("utf-8")
        except KeyError:
            return None


DistributedDulwichEngine = create_distributed(DulwichEngine)
PoolDulwichEngine = create_pool(DulwichEngine)
ThreadingDulwichEngine = create_threading(DulwichEngine)
