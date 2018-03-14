# Copyright (c) 2016 Universidade Federal Fluminense (UFF)
# Copyright (c) 2016 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""Content Database Pure Git"""
from __future__ import (absolute_import, print_function,
                        division, unicode_literals)
import os
import time

from .content_database import ContentDatabase
from dulwich.repo import Repo
from dulwich.objects import Tree, Commit, Blob, parse_timezone
from os.path import isdir
from . import git_system


class ContentDatbaseDulwich(ContentDatabase):
    """Content database that uses git library Dulwich"""

    def __init__(self, persistence_config):
        super(ContentDatbaseDulwich, self).__init__(persistence_config)
        self.__repo = None
        self.__tree = Tree()
        self.__commit_name_email = 'Noworkflow <now@nowokflow.com>'
        self.__commit_encoding = 'UTF-8'

    def mock(self, config):  # pylint: disable=unused-argument, no-self-use
        '''"""Mock storage for tests"""
        self.temp = {}

        def put(self, content):
            """Mock put"""
            hash_code = hashlib.sha1(content).hexdigest()
            self.temp[hash_code] = content
            return hash_code

        def get(self, content_hash):
            """Mock get"""
            return self.temp[content_hash]
        ContentDatabaseStandart.put = put
        ContentDatabaseStandart.get = get'''
        pass

    def connect(self, config):
        """Create content directory"""
        if not isdir(self.content_path):
            os.makedirs(self.content_path)
            Repo.init_bare(self.content_path)
            self.__create_initial_commit()


    def put(self, content):
        """Put content in the content database

        Return: content hash code

        Arguments:
        content -- binary text to be saved
        """
        object_store = self.__get_repo().object_store
        blob = Blob.from_string(content)
        object_store.add_object(blob)
        self.__tree.add(blob.id, 0o100644, blob.id)

        #print("blob {0}".format(blob.id.decode("ascii")))

        return blob.id.decode("ascii")

    def find_subhash(self, content_hash):
        return None

    def get(self, content_hash):
        """Get content from the content database

        Return: content

        Arguments:
        content_hash -- content hash code
        """
        return self.__get_repo().__getitem__(content_hash.encode()).as_pretty_string()

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
        author = self.__commit_name_email.encode()
        commit.author = commit.committer = author
        commit.commit_time = commit.author_time = int(time.time())
        tz = parse_timezone(time.strftime("%z").encode())[0]
        commit.commit_timezone = commit.author_timezone = tz
        commit.encoding = self.__commit_encoding.encode()
        commit.message = message.encode()

        return commit

    def commit_content(self, message):
        """Commit the current files of content database

                        Arguments:
                        message -- commit message
                        """

        object_store = self.__get_repo().object_store
        object_store.add_object(self.__tree)
        commit = self.__create_commit_object(message, self.__tree, self.__get_master_ref())
        #print("tree {0}".format(self.__tree.id.decode("ascii")))
        #print("commit {0}".format(commit.id.decode("ascii")))
        object_store.add_object(commit)
        self.__set_master_ref(commit.id)

    def __create_initial_commit(self):
        """Create the initial commit of the git repository
        """
        object_store = self.__get_repo().object_store
        empty_tree = Tree()
        object_store.add_object(empty_tree)
        initial_commit = self.__create_commit_object('Initial Commit', empty_tree)
        object_store.add_object(initial_commit)
        self.__set_master_ref(initial_commit.id)

    def __get_master_ref(self):
        """Returns the master ref commit hash
        """
        return self.__get_repo().get_refs()[b'refs/heads/master']

    def __set_master_ref(self, commit_hash):
        """Set the master ref commit
                        Arguments:
                        commit_hash -- hash of commit object
                        """
        self.__get_repo().refs[b'refs/heads/master'] = commit_hash

    def gc(self, aggressive=False):
        print("content path: {0}".format(self.content_path))
        git_system.garbage_collection(self.content_path, aggressive)

    def __get_repo(self):
        """Returns the current git repository object"""
        if self.__repo is None:
            self.__repo = Repo(self.content_path)
        return self.__repo
