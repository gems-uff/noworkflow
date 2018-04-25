# Copyright (c) 2016 Universidade Federal Fluminense (UFF)
# Copyright (c) 2016 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""Content Database Factory"""
from __future__ import (absolute_import, print_function,
                        division, unicode_literals)

from .content_database_standart import ContentDatabaseStandart
from .content_database_pure_git import ContentDatabasePureGit
from .content_database_dulwich import ContentDatabaseDulwich
from .content_database_pygit import ContentDatabasePyGit
from .content_database_pygit_db import ContentDatabasePyGitDB
from .content_database_pygit_threading import ContentDatabasePyGitThreading
from .content_database_pygit_db_hybrid import ContentDatabasePyGitDBHybrid
from .content_database_pygit_db_hybrid_threading import ContentDatabasePyGitDBHybridThreading


CONTENT_GIT_DIRNAME = "content.git"
CONTENT_DIRNAME = "content"


class ContentDatabaseFactory(object):

    @staticmethod
    def factory(persistence_config):

        persistence_config.content_dir = CONTENT_GIT_DIRNAME
        return ContentDatabasePyGitDBHybridThreading(persistence_config)


