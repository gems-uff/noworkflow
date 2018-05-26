import os
import hashlib
import hashlib
import os

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
        self.__repo = None
        self.__tree_builder = None
        self.__commit_name = 'Noworkflow'
        self.__commit_email = 'noworkflow@noworkflow.com'
        self.tasks = None
        self.consumers = []
        self.num_consumers = None

    def connect(self):
        """Create content directory"""

        if not isdir(self.content_path):
            os.makedirs(self.content_path)
            init_repository(self.content_path, bare=True)
            self.__create_initial_commit()

        self.num_consumers = cpu_count()
        self.tasks = JoinableQueue()
        self.consumers = []

        for i in xrange(0, self.num_consumers):
            repo = Repository(self.content_path)
            tree = repo.TreeBuilder()
            consumer = Worker(task_queue=self.tasks, repo=repo,
                              tree=tree)
            self.consumers.append(consumer)
            consumer.start()

    def get(self, content_hash):
        """Get content from the content database

        Return: content

        Arguments:
        content_hash -- content hash code
        """
        return_data = self.__get_repo()[content_hash].data
        return return_data

    def put(self, content):
        """Put content in the content database

        Return: content hash code

        Arguments:
        content -- binary text to be saved
        """

        self.tasks.put(content)

        content_hash = self.__get_hash_from_content(content)

        return content_hash

    def __get_hash_from_content(self, content):
        git_content = b'blob ' + str(len(content)) + b'\0'
        hash = hashlib.sha1(git_content + content).hexdigest()
        return hash

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

        return self.__create_commit_object(message, self.__get_tree_builder().write())

    def __get_repo(self):
        """Returns the current git repository object"""
        if self.__repo is None:
            self.__repo = Repository(self.content_path)
        return self.__repo

    def __get_tree_builder(self):
        if self.__tree_builder is None:
            repo = self.__get_repo()
            self.__tree_builder = repo.TreeBuilder()
        return self.__tree_builder

    def __create_initial_commit(self):
        """Create the initial commit of the git repository
        """
        empty_tree = self.__get_tree_builder().write()

        self.__create_commit_object('Initial Commit', empty_tree)

    def __create_commit_object(self, message, tree):
        """creates a commit object

                Return: Commit object

                Arguments:
                message -- commit message
                tree - commit tree object
                parent - hash of commit parent
                """

        references = list(self.__get_repo().references)

        master_ref = self.__get_repo().lookup_reference("refs/heads/master") if len(references) > 0 else None

        parents = []
        if master_ref is not None:
            parents = [master_ref.peel().id]

        author = Signature(self.__commit_name, self.__commit_email)
        return self.__get_repo().create_commit('refs/heads/master', author, author, message, tree, parents)


class Worker(Process):

    def __init__(self, task_queue, repo, tree):
        Process.__init__(self)
        self.task_queue = task_queue
        self.repo = repo
        self.tree = tree

    def run(self):
        while True:
            next_content = self.task_queue.get()

            if next_content is None:
                # Poison pill means shutdown
                self.task_queue.task_done()
                break

            object_id = self.repo.create_blob(next_content)
            self.tree.insert(str(object_id), object_id, GIT_FILEMODE_BLOB)
            self.task_queue.task_done()
        return
