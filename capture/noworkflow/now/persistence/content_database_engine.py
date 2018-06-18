import hashlib
import os
import time

from . import git_system
from os.path import join, isdir, isfile
from pygit2 import init_repository, GIT_FILEMODE_BLOB, Repository, Signature
from dulwich.repo import Repo
from dulwich.objects import Tree, Commit, Blob, parse_timezone
from multiprocessing import Process, JoinableQueue, cpu_count, Manager


class ContentDatabaseEngine(object):
    def __init__(self, content_path):
        self.content_path = content_path

    def put(self, file_name, content):
        pass

    def get(self, content_hash):
        pass


class StandardContentDatabaseEngine(ContentDatabaseEngine):
    def __init__(self, content_path):
        super(StandardContentDatabaseEngine, self).__init__(content_path)
        self.std_open = open  # Original Python open function.

    def mock(self):
        """Mock storage for tests"""
        self.temp = {}

        def put(self, content):
            """Mock put"""
            hash_code = hashlib.sha1(content).hexdigest()
            self.temp[hash_code] = content
            return hash_code

        def get(self, content_hash):
            """Mock get"""
            return self.temp[content_hash]

        StandardContentDatabaseEngine.put = put
        StandardContentDatabaseEngine.get = get

    def connect(self, should_mock=False):
        """Create content directory"""
        if not should_mock and not isdir(self.content_path):
            os.makedirs(self.content_path)

    def put(self, file_name, content):
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
        content_filename = content_hash[2:]
        content_dir = join(self.content_path, content_dirname)
        if not isdir(content_dir):
            return None
        for _, _, filenames in os.walk(content_dir):
            for name in filenames:
                if name.startswith(content_filename):
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


class GitContentDatabaseEngine(ContentDatabaseEngine):

    def __init__(self, content_path):
        super(GitContentDatabaseEngine, self).__init__(content_path)
        self._commit_name = 'Noworkflow'
        self._commit_email = 'noworkflow@noworkflow.com'
        self.name_counter = {}

    def connect(self):
        pass

    def get(self, content_hash):
        pass

    def commit_content(self, message):
        pass

    def gc(self, aggressive=False):
        git_system.garbage_collection(self.content_path, aggressive)

    def _get_hash_from_content(self, content):
        git_content = b'blob ' + str(len(content)) + b'\0'
        hash = hashlib.sha1(git_content + content).hexdigest()
        return hash


class DistributedPyGitContentDatabaseEngine(GitContentDatabaseEngine):

    def __init__(self, content_path):
        super(DistributedPyGitContentDatabaseEngine, self).__init__(content_path)
        self.tasks = None
        self.consumers = []
        self.num_consumers = None
        self.object_hashes = None
        self.processes_started = True

    def connect(self):
        """Create content directory"""
        if not isdir(self.content_path):
            init_repository(self.content_path, bare=True)
            self._create_initial_commit()

    def get(self, content_hash):
        """Get content from the content database

        Return: content

        Arguments:
        content_hash -- content hash code
        """
        return_data = PyGitRepoObjects(self.content_path).repo[content_hash].data
        return return_data

    def start_processes(self):
        self.object_hashes = Manager().dict()

        self.num_consumers = cpu_count()
        self.tasks = JoinableQueue()
        self.consumers = []

        for i in xrange(0, self.num_consumers):
            consumer = PyGitWorker(task_queue=self.tasks, content_path=self.content_path)
            self.consumers.append(consumer)
            consumer.start()
        self.processes_started = False

    def put(self, file_name, content):
        """Put content in the content database

        Return: content hash code

        Arguments:
        content -- binary text to be saved
        """

        if self.processes_started:
            self.start_processes()

        if file_name in self.name_counter:
            self.name_counter[file_name] += 1
            file_name = file_name + ' - v' + str(self.name_counter[file_name])
        else:
            self.name_counter[file_name] = 1

        self.tasks.put((content, file_name, self.object_hashes,))

        content_hash = self._get_hash_from_content(content)

        return content_hash

    def commit_content(self, message):
        """Commit the current files of content database

                        Arguments:
                        message -- commit message

           """
        # Add a poison pill for each consumer
        for i in xrange(self.num_consumers):
            self.tasks.put(None)

        # Wait for all of the tasks to finish
        self.tasks.join()

        for key, value in self.object_hashes.items():
            PyGitRepoObjects(self.content_path).tree_builder.insert(key, value, GIT_FILEMODE_BLOB)

        commit_oid = self._create_commit_object(message, PyGitRepoObjects(self.content_path).tree_builder.write())

        return commit_oid

    def _create_initial_commit(self):
        """Create the initial commit of the git repository
        """
        empty_tree = PyGitRepoObjects(self.content_path).tree_builder.write()

        self._create_commit_object('Initial Commit', empty_tree)

    def _create_commit_object(self, message, tree):
        """creates a commit object

                Return: Commit object

                Arguments:
                message -- commit message
                tree - commit tree object
                parent - hash of commit parent
                """

        references = list(PyGitRepoObjects(self.content_path).repo.references)

        master_ref = PyGitRepoObjects(self.content_path).repo.lookup_reference("refs/heads/master") if len(
            references) > 0 else None

        parents = []
        if master_ref is not None:
            parents = [master_ref.peel().id]

        author = Signature(self._commit_name, self._commit_email)
        return PyGitRepoObjects(self.content_path).repo.create_commit('refs/heads/master', author, author, message,
                                                                      tree,
                                                                      parents)


class DulwichContentDatabaseEngine(GitContentDatabaseEngine):

    def __init__(self, content_path):
        super(DulwichContentDatabaseEngine, self).__init__(content_path)
        self._commit_encoding = 'UTF-8'

    def connect(self):
        """Create content directory"""
        if not isdir(self.content_path):
            os.makedirs(self.content_path)
            Repo.init_bare(self.content_path)
            self.__create_initial_commit()

    def put(self, file_name, content):
        """Put content in the content database

        Return: content hash code

        Arguments:
        content -- binary text to be saved
        """
        object_store = DulwichRepoObjects(self.content_path).repo.object_store
        blob = Blob.from_string(content)
        object_store.add_object(blob)

        if file_name in self.name_counter:
            self.name_counter[file_name] += 1
            file_name = file_name + ' - v' + str(self.name_counter[file_name])
        else:
            self.name_counter[file_name] = 1

        file_name_hash = hashlib.sha1(file_name).hexdigest()
        file_name_hash = hashlib.sha1(file_name).hexdigest()

        DulwichRepoObjects(self.content_path).tree.add(file_name_hash, 0o100644, blob.id)

        return blob.id.decode("ascii")

    def get(self, content_hash):
        """Get content from the content database

        Return: content

        Arguments:
        content_hash -- content hash code
        """

        return_data = DulwichRepoObjects(self.content_path).repo.__getitem__(content_hash.encode()).as_pretty_string()

        return return_data

    def __create_commit_object(self, message, tree, parent=None):
        """creates a commit object

                Return: Commit object

                Arguments:
                message -- commit message
                tree - commit tree object
                parent - hash of commit parent
                """
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

    def commit_content(self, message):
        """Commit the current files of content database

                        Arguments:
                        message -- commit message
                        """

        object_store = DulwichRepoObjects(self.content_path).repo.object_store
        object_store.add_object(DulwichRepoObjects(self.content_path).tree)
        commit = self.__create_commit_object(message, DulwichRepoObjects(self.content_path).tree,
                                             self.__get_master_ref())
        object_store.add_object(commit)
        self.__set_master_ref(commit.id)

    def __create_initial_commit(self):
        """Create the initial commit of the git repository
        """
        object_store = DulwichRepoObjects(self.content_path).repo.object_store
        empty_tree = Tree()
        object_store.add_object(empty_tree)
        initial_commit = self.__create_commit_object('Initial Commit', empty_tree)
        object_store.add_object(initial_commit)
        self.__set_master_ref(initial_commit.id)

    def __get_master_ref(self):
        """Returns the master ref commit hash
        """
        return DulwichRepoObjects(self.content_path).repo.get_refs()[b'refs/heads/master']

    def __set_master_ref(self, commit_hash):
        """Set the master ref commit
                        Arguments:
                        commit_hash -- hash of commit object
                        """
        DulwichRepoObjects(self.content_path).repo.refs[b'refs/heads/master'] = commit_hash


class DulwichRepoObjects(object):
    __instance = None

    def __new__(cls, content_path):
        if DulwichRepoObjects.__instance is None:
            repo = Repo(content_path)
            tree = Tree()
            DulwichRepoObjects.__instance = object.__new__(cls)
            DulwichRepoObjects.__instance.repo = repo
            DulwichRepoObjects.__instance.tree = tree
        return DulwichRepoObjects.__instance


class PyGitWorker(Process):

    def __init__(self, task_queue, content_path):
        Process.__init__(self)
        self.task_queue = task_queue
        self.content_path = content_path

    def run(self):
        while True:

            queue_content = self.task_queue.get()

            if queue_content is None:
                # Poison pill means shutdown
                self.task_queue.task_done()
                break

            next_content, name, object_hashes = queue_content

            content_hash = PyGitRepoObjects(self.content_path).repo.create_blob(next_content)

            file_name_hash = hashlib.sha1(name).hexdigest()

            object_hashes[file_name_hash] = str(content_hash)

            self.task_queue.task_done()
        return


class PyGitRepoObjects(object):
    __instance = None

    def __new__(cls, content_path):
        if PyGitRepoObjects.__instance is None:
            repo = Repository(content_path)
            PyGitRepoObjects.__instance = object.__new__(cls)
            PyGitRepoObjects.__instance.repo = repo
            PyGitRepoObjects.__instance.tree_builder = repo.TreeBuilder()
        return PyGitRepoObjects.__instance
