# Copyright (c) 2026 Universidade Federal Fluminense (UFF)
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""Persistence wiring shared by both test runners"""
from __future__ import (absolute_import, print_function,
                        division, unicode_literals)

from ...now.persistence import persistence_config


def connect_in_memory():
    """Connect the persistence layer to in-memory stores

    The order of the calls matters. ``mock()`` needs the content engine,
    which only exists after a path is set, and ``connect()`` reads
    ``should_mock`` while opening the relational store: mocking after
    connecting, as the suite used to do, opened a real
    ``.noworkflow/db.sqlite`` in the current directory that persisted
    between runs. The engine is pinned to ``plain`` because the git engines
    open a repository on connect even when mocked.
    """
    persistence_config.content_engine = "plain"
    persistence_config.path = "."
    persistence_config.mock()
    persistence_config.connect()
