from __future__ import (absolute_import, print_function,
                        division, unicode_literals)
import os
from multiprocessing import Process, JoinableQueue, cpu_count
from .content_database import ContentDatabase
from . import git_system
from os.path import isdir
from pygit2 import init_repository, GIT_FILEMODE_BLOB, Repository, hash, Signature
from ..utils import func_profiler


class Consumer(Process):

    def __init__(self, task_queue, repo, tree):
        Process.__init__(self)
        self.task_queue = task_queue
        self.repo = repo
        self.tree = tree

    def run(self):
        while True:
            next_task_content = self.task_queue.get()

            if next_task_content is None:
                # Poison pill means shutdown
                self.task_queue.task_done()
                break
            create_git_objects(next_task_content, self.repo, self.tree)
            self.task_queue.task_done()
        return


class Task(object):
    def __init__(self, content):
        self.content = content

    def __call__(self, repo, tree):
        object_id = repo.create_blob(self.content)
        tree.insert(str(object_id), object_id, GIT_FILEMODE_BLOB)


def create_git_objects(content, repo=None, tree=None):
    object_id = repo.create_blob(content)
    tree.insert(str(object_id), object_id, GIT_FILEMODE_BLOB)

class ContentDatabasePyGitProcessingQueue(ContentDatabase):
    """Content database that uses git library PyGit2"""

    def __init__(self, persistence_config):
        super(ContentDatabasePyGitProcessingQueue, self).__init__(persistence_config)
        self.__repo = None
        self.__tree_builder = None
        self.__commit_name = 'Noworkflow'
        self.__commit_email = 'noworkflow@noworkflow.com'
        self.tasks = None
        self.consumers = []
        self.num_consumers = None

    def __str__(self):
        return "ContentDatabasePyGitProcessingQueue"

    def connect(self, config):
        """Create content directory"""

        if not isdir(self.content_path):
            os.makedirs(self.content_path)
            init_repository(self.content_path, bare=True)
            self.__create_initial_commit()

        self.num_consumers = cpu_count()
        self.tasks = JoinableQueue()
        self.consumers = []

        for i in xrange(0,self.num_consumers):
            repo = Repository(self.content_path)
            tree = repo.TreeBuilder()
            consumer = Consumer(task_queue=self.tasks, repo=repo,
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

    #@func_profiler.profile
    def put(self, content):
        """Put content in the content database

        Return: content hash code

        Arguments:
        content -- binary text to be saved
        """
        self.tasks.put(content)

        content_hash = str(hash(content))

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

        return self.__create_commit_object(message, self.__get_tree_builder().write())

    def gc(self, aggressive=False):
        print("content path: {0}".format(self.content_path))
        git_system.garbage_collection(self.content_path, aggressive)

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
