# Copyright (c) 2019 Universidade Federal Fluminense (UFF)
# Copyright (c) 2019 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""Content Database"""
from __future__ import (absolute_import, print_function,
                        division, unicode_literals)

import importlib
from os.path import join, isdir
from .content.plain_engine import STANDARD_DATABASE_DIR
from ..utils.io import print_msg

class ContentDatabase(object):
    """Content Database deal with storage of file content in disk"""

    def __init__(self, persistence_config):
        self.content_path = None  # Base path for storing content of files
        persistence_config.add(self)
        self.content_database_engine = None

        self.content_engines = {
            "plain": "noworkflow.now.persistence.content.plain_engine.PlainEngine",
            "sequential_plain": "noworkflow.now.persistence.content.plain_engine.PlainEngine",
            "distributed_plain": "noworkflow.now.persistence.content.plain_engine.PlainEngine",
            "pool_plain": "noworkflow.now.persistence.content.plain_engine.PlainEngine",
            "threading_plain": "noworkflow.now.persistence.content.plain_engine.PlainEngine",
            "pygit": "noworkflow.now.persistence.content.pygit_engine.DistributedPyGitEngine",
            "sequential_pygit": "noworkflow.now.persistence.content.pygit_engine.PyGitEngine",
            "distributed_pygit": "noworkflow.now.persistence.content.pygit_engine.DistributedPyGitEngine",
            "pool_pygit": "noworkflow.now.persistence.content.pygit_engine.PoolPyGitEngine",
            "threading_pygit": "noworkflow.now.persistence.content.pygit_engine.ThreadingPyGitEngine",
            "dulwich": "noworkflow.now.persistence.content.dulwich_engine.DulwichEngine",
            "sequential_dulwich": "noworkflow.now.persistence.content.dulwich_engine.DulwichEngine",
            "distributed_dulwich": "noworkflow.now.persistence.content.dulwich_engine.DistributedDulwichEngine",
            "pool_dulwich": "noworkflow.now.persistence.content.dulwich_engine.PoolDulwichEngine",
            "threading_dulwich": "noworkflow.now.persistence.content.dulwich_engine.ThreadingDulwichEngine",
            "puregit": "noworkflow.now.persistence.content.puregit_engine.PureGitEngine",
            "gitdb": "noworkflow.now.persistence.content.gitdb_engine.GitDBPyGitEngine",
        }

    def define_engine(self, config):
        if config.content_engine is not None:
            engine = config.content_engine
        elif isdir(join(config.provenance_path, STANDARD_DATABASE_DIR)):
            # Use plain directory
            engine = "plain"
        else:
            # Use git
            try:
                import pygit2
                engine = "pygit"
            except ImportError:
                try:
                    import dulwich
                    engine = "dulwich"
                except ImportError:
                    # Use plain
                    engine = "plain"
        if '.' in engine:
            full_name = engine
        else:
            full_name = self.content_engines.get(engine, self.content_engines["plain"])
        print_msg("using content engine " + full_name)
        module_name, class_name = full_name.rsplit(".", 1)
        module = importlib.import_module(module_name) 
        cls = getattr(module, class_name)
        self.content_database_engine = cls(config)
        

    def __getattr__(self, attr):
        return getattr(self.content_database_engine, attr)

    def set_path(self, config):
        if self.content_database_engine is None:
            self.define_engine(config)
        self.content_database_engine.set_path(config)


    def connect(self, config):
        if self.content_database_engine is None:
            self.define_engine(config)
        self.content_database_engine.connect()
