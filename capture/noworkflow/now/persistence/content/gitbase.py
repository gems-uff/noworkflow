import os
import hashlib

from collections import Counter

from ...utils.cross_version import bytes_string
from . import git_system
from .base import ContentDatabaseEngine


GIT_DATABASE_DIR = 'content.git'


class GitContentDatabaseEngine(ContentDatabaseEngine):
    def __init__(self, config):
        super(GitContentDatabaseEngine, self).__init__(config)
        self._commit_name = 'Noworkflow'
        self._commit_email = 'noworkflow@noworkflow.com'
        self._commit_ref = 'refs/heads/master'
        self._initial_message = "Initial Commit"
        self.name_counter = Counter()
        self.base_path = None
        self.user_path = os.path.expanduser("~")
        self._max_filename_size = 4096
        self.object_hashes = {}

    def set_path(self, config):
        """Set content path"""
        self.content_path = os.path.join(config.provenance_path, GIT_DATABASE_DIR)
        self.base_path = os.path.abspath(config.base_path)

    def gc(self, aggressive=False):
        git_system.garbage_collection(self.content_path, aggressive)

    def commit_content(self, message):
        """Commit the current files of content database"""
        self.close()
        trees = {'': self.new_tree('')}

        for key, value in self.object_hashes.items():
            basename = os.path.basename(key)
            self.insert_blob(self._get_tree(trees, key), basename, value)

        tree_hashes = {}
        tree_keys = sorted(list(trees.keys()), key=len, reverse=True)
        for tree in tree_keys:
            dirname = os.path.dirname(tree)
            basename = os.path.basename(tree)
            tree_hashes[tree] = value = self.write_tree(trees[tree])
            if basename != '':
                self.insert_tree(trees[dirname], basename, value)

        return self.create_commit_object(message, tree_hashes[''])

    def _increment(self, filename):
        """Increment filename to avoid collisions"""
        filename = filename.strip()
        self.name_counter[filename] += 1
        count = self.name_counter[filename] 
        if count == 1:
            return filename
        return "{} - v{}".format(filename, count)

    def _inc_name(self, filename):
        """Define name for file in repository"""
        filename = os.path.abspath(filename)
        if filename.startswith(self.base_path):
            filename = os.path.relpath(filename, self.base_path)
        elif filename.startswith(self.user_path):
            filename = os.path.join("noworkflow_home", os.path.relpath(filename, self.user_path))
        else:
            drive, rest = os.path.splitdrive(filename)
            if rest.startswith("/"):
                rest = rest[1:]
            filename = os.path.join("noworkflow_root", drive, rest)
        result = self._increment(filename)
        if len(result) > self._max_filename_size:
            filename = os.path.join("noworkflow_long", os.path.basename(filename))
            result = self._increment(filename)
            if len(result) > self._max_filename_size:
                filename = os.path.join("noworkflow_long", "long")
                result = self._increment(filename)
        return result

    def _get_hash_from_content(self, content):
        """Calculate hash from content"""
        git_content = bytes_string('blob {}'.format((len(content)))) + b'\0'
        hash = hashlib.sha1(git_content + content).hexdigest()
        return hash

    def _get_tree(self, trees, key):
        """Build git tree recursively"""
        original = dirname = os.path.dirname(key)
        while dirname not in trees:
            trees[dirname] = self.new_tree(dirname)
            dirname = os.path.dirname(dirname)
        return trees[original]

    def create_initial_commit(self):
        """Create the initial commit of the git repository"""
        raise NotImplementedError("Implement in subclass")

    def create_commit_object(self, message, tree):
        """Create a commit object"""
        raise NotImplementedError("Implement in subclass")
    
    def new_tree(self, parent):
        """Create new git tree"""
        raise NotImplementedError("Implement in subclass")

    def insert_blob(self, tree, basename, value):
        """Insert blob into tree"""
        raise NotImplementedError("Implement in subclass")

    def insert_tree(self, tree, basename, value):
        """Insert tree into tree"""
        raise NotImplementedError("Implement in subclass")

    def write_tree(self, tree):
        """Write tree to git directory"""
        raise NotImplementedError("Implement in subclass")
