import os
import hashlib
import time
import io
import posixpath

from dulwich import file
from dulwich.repo import Repo
from dulwich.objects import Tree
from dulwich.objects import Blob
from dulwich.objects import Commit
from dulwich.objects import parse_timezone
from dulwich.objectspec import scan_for_short_id

from .gitbase import GitContentDatabaseEngine
from .parallel import create_distributed, create_pool, create_threading, NullLock
from . import safeopen

class DulwichEngine(GitContentDatabaseEngine):

    def __init__(self, config):
        super(DulwichEngine, self).__init__(config)
        self._commit_encoding = 'UTF-8'
        self.repo = None
        self.lock = NullLock()

    def connect(self, config):
        """Create content directory"""
        if not config.should_mock and not os.path.isdir(self.content_path):
            os.makedirs(self.content_path)
            Repo.init_bare(self.content_path)
            self.repo = Repo(self.content_path)
            self._commit_ref = self.branch_ref(self._default_branch)
            self._set_head(self._commit_ref)
            self.create_initial_commit()
        else:
            self.repo = Repo(self.content_path)
            self._commit_ref = self._current_branch_ref()

    @staticmethod
    def do_put(content_path, object_hashes, lock, content, filename):
        """Perform put operation. This is used in the distributed wrapper"""
        with safeopen.use_safe_open():
            object_store = Repo(content_path).object_store
            blob = Blob.from_string(content)
            with lock:
                object_store.add_object(blob)
            result = object_hashes[filename] = blob.id.decode("ascii")
            return result

    def put_attr(self, content, filename):
        """Return attributes for the do_put operation"""
        filename = self._inc_name(filename)
        return (
            self.content_path, self.object_hashes, self.lock, content, filename
        )

    def put(self, content, filename="generic"):  # pylint: disable=method-hidden
        """Put content in the content database"""
        return self.do_put(*self.put_attr(content, filename))

    def get(self, content_hash):  # pylint: disable=method-hidden
        """Get content from the content database"""
        with self.use_safe_open():
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
        with self.use_safe_open():
            object_store = self.repo.object_store
            empty_tree = Tree()
            object_store.add_object(empty_tree)
            self.create_commit_object(self._initial_message, empty_tree.id)

    def create_commit_object(self, message, tree, trial_id=None):
        """Create a commit object"""
        with self.use_safe_open(): 
            self._commit_ref = self._current_branch_ref()
            branch_ref = self._commit_ref.encode("utf-8")
            master_ref = self.repo.get_refs().get(branch_ref, None)
            
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
            self.repo.refs[branch_ref] = commit.id
            if trial_id:
                self.repo.refs[self.trial_ref(trial_id).encode("utf-8")] = commit.id

            return commit.id

    def commit_content(self, message, trial_id=None):
        """Commit the current files and update branch/trial refs"""
        commit_id = super(DulwichEngine, self).commit_content(message)
        if trial_id:
            self.repo.refs[self.trial_ref(trial_id).encode("utf-8")] = commit_id
        return commit_id

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

    # Branch prototype API

    @staticmethod
    def _to_text(value):
        if value is None:
            return None
        if isinstance(value, bytes):
            return value.decode("utf-8")
        return value

    @staticmethod
    def _to_hex(value):
        if value is None:
            return None
        if isinstance(value, bytes):
            return value.decode("ascii")
        return str(value)

    @staticmethod
    def _valid_branch_name(name):
        return (
            name and
            ".." not in name and
            not name.startswith("/") and
            not name.endswith("/") and
            not name.endswith(".lock") and
            all(ch not in name for ch in " ~^:?*[\\")
        )

    def branch_ref(self, name):
        """Return a full Git branch ref"""
        if not self._valid_branch_name(name):
            raise RuntimeError("invalid branch name: {}".format(name))
        return "refs/heads/{}".format(name)

    def trial_ref(self, trial_id):
        """Return a full noWorkflow trial ref"""
        return self._trial_ref_prefix + str(trial_id)

    def _set_head(self, branch_ref):
        """Point HEAD at a branch ref"""
        ref = branch_ref.encode("utf-8")
        try:
            self.repo.refs.set_symbolic_ref(b"HEAD", ref)
        except AttributeError:
            with open(os.path.join(self.content_path, "HEAD"), "wb") as fil:
                fil.write(b"ref: " + ref + b"\n")
        self._commit_ref = branch_ref

    def _current_branch_ref(self):
        """Return current branch ref, upgrading old stores lazily"""
        try:
            head = self.repo.refs.read_ref(b"HEAD")
        except (AttributeError, KeyError):
            head = None
        head = head.decode("utf-8")
        if head and head.startswith("refs/heads/"):
            return head

        refs = self.repo.get_refs()
        for candidate in ("refs/heads/master", "refs/heads/main"):
            if candidate in refs:
                self._set_head(candidate)
                return candidate

        branch_ref = self.branch_ref(self._default_branch)
        self._set_head(branch_ref)
        return branch_ref

    def current_branch(self):
        """Return the current branch name"""
        ref = self._current_branch_ref()
        return ref.rsplit("/", 1)[-1]

    def branches(self):
        """Return branch names in content.git"""
        result = []
        for ref in self.repo.get_refs():
            if ref.startswith("refs/heads/"):
                result.append(ref.rsplit("/", 1)[-1])
        return sorted(result)


    def get_commit_id_by_trial_id(self, trial_id):
        """Return commit id for a trial ref"""
        return self.repo.get_refs().get(self.trial_ref(trial_id).encode("utf-8"))

    def get_trial_id_by_commit_id(self, commit_id):
        """Find trial id by commit id"""
        if not commit_id:
            return None
        wanted = self._to_hex(commit_id)
        prefix = self._trial_ref_prefix
        for ref, value in self.repo.get_refs().items():
            ref = self._to_text(ref)
            if ref.startswith(prefix) and value == commit_id:
                return ref[len(prefix):]
        return None

    def get_branch_head_trial_id(self, name=None):
        """Return trial_id at the named branch head"""
        """If no name is given, return trial_id current branch head"""
        return self.get_trial_id_by_commit_id(self.get_branch_head_commit_id(name))

    def get_branch_head_commit_id(self, name=None):
        """Return commit_id at the named branch head"""
        """If no name is given, return commit_id current branch head"""
        branch_ref = self.branch_ref(name) if name else self._current_branch_ref()
        commit_id = self.repo.get_refs().get(branch_ref.encode("utf-8"))
        return commit_id

    def create_branch(self, name, commit_id):
        """Create branch pointing to commit id"""
        if not commit_id:
            raise RuntimeError("cannot create branch without a commit")
        branch_ref = self.branch_ref(name)
        if branch_ref in self.repo.get_refs():
            raise RuntimeError("branch already exists: {}".format(name))
        self.repo.refs[branch_ref] = commit_id.encode("ascii")

    def switch_branch(self, name):
        """Switch HEAD to branch"""
        branch_ref = self.branch_ref(name)
        if branch_ref not in self.repo.get_refs():
            raise RuntimeError("branch not found: {}".format(name))
        self._set_head(branch_ref)

    def rename_branch(self, old, new):
        """Rename a branch ref"""
        old_ref = self.branch_ref(old)
        new_ref = self.branch_ref(new)
        refs = self.repo.get_refs()
        old_key = old_ref.encode("utf-8")
        new_key = new_ref.encode("utf-8")
        if old_key not in refs:
            raise RuntimeError("branch not found: {}".format(old))
        if new_key in refs:
            raise RuntimeError("branch already exists: {}".format(new))
        self.repo.refs[new_key] = refs[old_key]
        del self.repo.refs[old_key]
        if self._current_branch_ref() == old_ref:
            self._set_head(new_ref)

    def ensure_branch_for_trial(self, trial_id):
        """Create and switch to an automatic branch for a restored trial"""
        current_trial = self.current_branch_trial()
        if current_trial == str(trial_id):
            return self.current_branch()

        commit_id = self.trial_commit(trial_id)
        if not commit_id:
            return self.current_branch()

        base = "now-diverge-{}".format(str(trial_id)[:8])
        name = base
        index = 1
        existing = set(self.branches())
        while name in existing:
            index += 1
            name = "{}-{}".format(base, index)
        self.create_branch(name, commit_id)
        self.switch_branch(name)
        return name

    def checkout_branch(self, name):
        """Switch branch and restore versioned files from its tree"""
        self.switch_branch(name)
        commit_id = self.branch_commit(name)
        if not commit_id:
            return
        commit = self.repo[commit_id.encode("ascii")]
        self._checkout_tree(commit.tree, "")

    def _tree_items(self, tree):
        if hasattr(tree, "iteritems"):
            return tree.iteritems()
        return tree.items()

    def _checkout_tree(self, tree_id, prefix):
        tree = self.repo[tree_id]
        for item in self._tree_items(tree):
            if len(item) == 3:
                name, mode, sha = item
            else:
                name, entry = item
                mode, sha = entry.mode, entry.sha
            relative = posixpath.join(prefix, name) if prefix else name
            obj = self.repo[sha]
            if isinstance(obj, Tree):
                self._checkout_tree(sha, relative)
            else:
                path = os.path.join(self.base_path, *relative.split("/"))
                parent = os.path.dirname(path)
                if parent:
                    os.makedirs(parent, exist_ok=True)
                with self.std_open(path, "wb") as fil:
                    fil.write(obj.as_raw_string())


DistributedDulwichEngine = create_distributed(DulwichEngine)
PoolDulwichEngine = create_pool(DulwichEngine)
ThreadingDulwichEngine = create_threading(DulwichEngine)
