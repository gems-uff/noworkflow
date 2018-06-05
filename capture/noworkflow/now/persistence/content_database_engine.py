import hashlib
import os
from . import git_system

from os.path import join, isdir, isfile
from pygit2 import init_repository, GIT_FILEMODE_BLOB, Repository, Signature
from multiprocessing import Process, JoinableQueue, cpu_count


class ContentDatabaseEngine(object):
    def __init__(self, content_path):
        self.content_path = content_path

    def put(self, content):
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

    def put(self, content):
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


class PyGitContentDatabaseEngine(ContentDatabaseEngine):

    def __init__(self, content_path):
        super(PyGitContentDatabaseEngine, self).__init__(content_path)
        self._repo = None
        self._tree_builder = None
        self._commit_name = 'Noworkflow'
        self._commit_email = 'noworkflow@noworkflow.com'

    def connect(self):
        if not isdir(self.content_path):
            os.makedirs(self.content_path)
            init_repository(self.content_path, bare=True)
            self._create_initial_commit()

    def get(self, content_hash):
        """Get content from the content database

        Return: content

        Arguments:
        content_hash -- content hash code
        """
        return_data = self._get_repo()[content_hash].data
        return return_data

    def commit_content(self, message):
        """Commit the current files of content database

                        Arguments:
                        message -- commit message
                        """

        return self._create_commit_object(message, self._get_tree_builder().write())

    def gc(self, aggressive=False):
        print("content path: {0}".format(self.content_path))
        git_system.garbage_collection(self.content_path, aggressive)

    def _get_repo(self):
        """Returns the current git repository object"""
        if self._repo is None:
            self._repo = Repository(self.content_path)
        return self._repo

    def _get_tree_builder(self):
        if self._tree_builder is None:
            repo = self._get_repo()
            self._tree_builder = repo.TreeBuilder()
        return self._tree_builder

    def _get_hash_from_content(self, content):
        git_content = b'blob ' + str(len(content)) + b'\0'
        hash = hashlib.sha1(git_content + content).hexdigest()
        return hash

    def _create_initial_commit(self):
        """Create the initial commit of the git repository
        """
        empty_tree = self._get_tree_builder().write()

        self._create_commit_object('Initial Commit', empty_tree)

    def _create_commit_object(self, message, tree):
        """creates a commit object

                Return: Commit object

                Arguments:
                message -- commit message
                tree - commit tree object
                parent - hash of commit parent
                """

        references = list(self._get_repo().references)

        master_ref = self._get_repo().lookup_reference("refs/heads/master") if len(references) > 0 else None

        parents = []
        if master_ref is not None:
            parents = [master_ref.peel().id]

        author = Signature(self._commit_name, self._commit_email)
        return self._get_repo().create_commit('refs/heads/master', author, author, message, tree, parents)


class DistributedPyGitContentDatabaseEngine(PyGitContentDatabaseEngine):

    def __init__(self, content_path):
        super(DistributedPyGitContentDatabaseEngine, self).__init__(content_path)
        self.tasks = None
        self.consumers = []
        self.num_consumers = None
        self.object_hashes = {}
        self.start_processes = True

    def connect(self):
        """Create content directory"""
        super(DistributedPyGitContentDatabaseEngine, self).connect()

    def put(self, name, content):
        """Put content in the content database

        Return: content hash code

        Arguments:
        content -- binary text to be saved
        """

        if self.start_processes:
            self.num_consumers = cpu_count()
            self.tasks = JoinableQueue()
            self.consumers = []

            repo = self._get_repo()

            for i in xrange(0, self.num_consumers):
                consumer = Worker(task_queue=self.tasks, repo=repo)
                self.consumers.append(consumer)
                consumer.start()
            self.start_processes = False

        self.tasks.put((content, name, self.object_hashes,))

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
            self._get_tree_builder().insert(key, value, GIT_FILEMODE_BLOB)

        return self._create_commit_object(message, self._get_tree_builder().write())


class Worker(Process):

    def __init__(self, task_queue, repo):
        Process.__init__(self)
        self.task_queue = task_queue
        self.repo = repo

    def run(self):
        while True:

            queue_content = self.task_queue.get()

            if queue_content is None:
                # Poison pill means shutdown
                self.task_queue.task_done()
                break

            next_content, name, object_hashes = queue_content

            file_name_hash = hashlib.sha1(name).hexdigest()

            object_id = self.repo.create_blob(next_content)
            object_hashes[file_name_hash] = object_id

            self.task_queue.task_done()
        return
