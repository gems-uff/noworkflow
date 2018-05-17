from __future__ import (absolute_import, print_function,
                        division, unicode_literals)
import os
from multiprocessing import Pool, cpu_count
from .content_database import ContentDatabase
from . import git_system
from os.path import isdir
from pygit2 import init_repository, GIT_FILEMODE_BLOB, Repository, hash
from pygit2 import Signature
from ..utils import func_profiler

CONTENT_LIMIT = 2000000


def insert_into_git_database(content_path, content):
    repo = Repository(content_path)
    repo.create_blob(content)


class ContentDatabasePyGitProcessing(ContentDatabase):
    """Content database that uses git library PyGit2"""

    def __init__(self, persistence_config):
        super(ContentDatabasePyGitProcessing, self).__init__(persistence_config)
        self.__repo = None
        self.__tree_builder = None
        self.__commit_name = 'Noworkflow'
        self.__commit_email = 'noworkflow@noworkflow.com'
        self.ids_to_insert = []
        self.pool = None

    def mock(self, config):
        pass

    def connect(self, config):
        """Create content directory"""

        if not isdir(self.content_path):
            os.makedirs(self.content_path)
            init_repository(self.content_path, bare=True)
            self.__create_initial_commit()

        self.pool = Pool(cpu_count())

    @func_profiler.profile
    def put(self, content):
        """Put content in the content database

        Return: content hash code

        Arguments:
        content -- binary text to be saved
        """

        id = str(hash(content))
        self.pool.apply_async(insert_into_git_database, (self.content_path, content,))

        self.ids_to_insert.append(id)
        return id

    def find_subhash(self, content_hash):
        return None

    def get(self, content_hash):
        """Get content from the content database

        Return: content

        Arguments:
        content_hash -- content hash code
        """
        return_data = self.__get_repo()[content_hash].data
        return return_data


    def commit_content(self, message):
        """Commit the current files of content database

                        Arguments:
                        message -- commit message
                        """
        for id in self.ids_to_insert:
            self.__get_tree_builder().insert(str(id), id, GIT_FILEMODE_BLOB)

        self.pool.close()
        self.pool.join()

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
