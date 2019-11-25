import os

from os.path import isdir
from . import git_system
from . import safeopen
from .gitbase import GitContentDatabaseEngine



class PureGitEngine(GitContentDatabaseEngine):

    def __init__(self, config):
        super(PureGitEngine, self).__init__(config)

    def connect(self, should_mock=False):
        """Create content directory"""
        if not should_mock and not isdir(self.content_path):
            git_system.init(self.content_path)
            self.create_initial_commit()

    @staticmethod
    def do_put(content_path, object_hashes, content, filename):
        """Perform put operation. This is used in the distributed wrapper"""
        with safeopen.restore_open():
            content_hash = git_system.hash_object(content, content_path)
            result = object_hashes[filename] = content_hash
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
        return git_system.get(content_hash, self.content_path)
 
    def gc(self):
        git_system.garbage_collection(self.content_path)

    def find_subhash(self, content_hash):
        """Find hash in database"""
        bytes_content_hash = content_hash.encode("utf-8")
        print(bytes_content_hash)
        objects = git_system.all_objects(self.content_path)
        print(objects)
        for obj in objects:
            print(obj)
            if obj.startswith(bytes_content_hash):
                return obj
        return None

    def create_initial_commit(self):
        """Create the initial commit of the git repository"""
        tree = git_system.write_tree(self.content_path)
        self.create_commit_object(self._initial_message, tree)

    def create_commit_object(self, message, tree):
        """Creates a commit object"""
        master_ref = git_system.show_ref(self._commit_ref, self.content_path)
        result = git_system.commit_tree(
            tree, message, self.content_path,
            parent=master_ref,
            author=(self._commit_name, self._commit_email)
        )
        git_system.update_ref(self._commit_ref, result, self.content_path)
        return result

    def new_tree(self, parent):
        if parent == '':
            git_system.rm_all(self.content_path)
        return Tree(parent, self.content_path)

    def insert_blob(self, tree, basename, value):
        """Insert blob into tree"""
        tree.insert_blob(basename, value)
    
    def insert_tree(self, tree, basename, value):
        """Pure-git commands to update tree allow paths on insert-blob. We do not need to break down trees"""
        pass

    def write_tree(self, tree):
        """Write tree to git directory"""
        return tree.write()

class Tree(object):

    def __init__(self, dirname, content_path):
        self.operations = []
        self.dirname = dirname
        self.content_path = os.path.join(content_path)

    def insert_blob(self, basename, value):
        self.operations.append((
            git_system.update_index,
            ("100644", value, os.path.join(self.dirname, basename), self.content_path)
        ))

    def write(self):
        for op, args in self.operations:
            op(*args)
        result = "auto"
        if self.dirname == '':
            result = git_system.write_tree(self.content_path)
            git_system.rm_all(self.content_path)
        return result
