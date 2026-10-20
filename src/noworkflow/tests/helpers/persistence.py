# Copyright (c) 2026 Universidade Federal Fluminense (UFF)
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""Persistence wiring shared by both test runners"""

from __future__ import absolute_import, division, print_function, unicode_literals

import contextlib
import os

from ...now.persistence import (
    content,
    persistence_config,
    relational,
    relational_database,
)


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


@contextlib.contextmanager
def connected_to(path):
    """Connect the persistence layer to the real store under ``path``

    In-process code that reads through ``noworkflow.now.persistence`` (the
    models, the patterns, the vis views) then sees the store of the project
    directory ``path`` (its ``.noworkflow``), with a ``plain`` content
    engine of its own whose ``get`` reads the store's content directory.
    On exit the in-memory stores that ``connect_in_memory`` set up come back
    untouched (``real_stores``).

    Nothing here writes to the store, but whatever the caller runs may;
    ``two_trial_project`` checks that a shared store stays as it was.
    """
    path = os.path.abspath(str(path))
    if not persistence_config._has_provenance(path):
        raise FileNotFoundError("no provenance store in {}".format(path))
    with real_stores():
        persistence_config.connect(path)
        yield


@contextlib.contextmanager
def real_stores():
    """Let in-process code connect the persistence layer to stores on disk

    Inside the block ``persistence_config.connect(path)`` opens the store
    under ``path`` and creates it when it is missing, as in a ``now``
    process: ``should_mock`` is off and the content engine is a new
    ``plain`` one (the in-memory one has a mocked ``put`` and ``get``).
    Nothing is connected on entry; ``connected_to`` connects to a store
    that must exist, and the IPython extension connects to the current
    directory when it loads.

    Code that connects again and again is covered: the magics connect on
    every call and never close what they replace. On exit every session
    the relational store made inside is removed, every SQLAlchemy engine
    created inside is disposed (both close the file: Windows cannot remove
    an open database), and the in-memory stores that ``connect_in_memory``
    set up come back untouched: the same SQLAlchemy engine (an in-memory
    SQLite database lives as long as its engine), the same sessions and the
    same mocked content engine. The blocks nest.
    """
    saved_config = (
        persistence_config.base_path,
        persistence_config.provenance_path,
        persistence_config.should_mock,
        persistence_config.content_engine,
    )
    saved_relational = (
        relational.db_path,
        relational.engine,
        relational._session_map,
    )
    saved_content = (content.content_path, content.content_database_engine)
    saved_create_engine = relational_database.create_engine
    saved_make_session = vars(relational).get("make_session")
    previous_make_session = relational.make_session
    engines, sessions = [], []

    def create_engine(*args, **kwargs):
        engine = saved_create_engine(*args, **kwargs)
        engines.append(engine)
        return engine

    def make_session():
        session = previous_make_session()
        sessions.append(session)
        return session

    relational_database.create_engine = create_engine
    relational.make_session = make_session
    content.content_database_engine = None
    persistence_config.should_mock = False
    persistence_config.content_engine = "plain"
    try:
        yield
    finally:
        relational_database.create_engine = saved_create_engine
        if saved_make_session is None:
            del relational.make_session
        else:
            relational.make_session = saved_make_session
        for session in sessions:
            session.remove()
        for engine in engines:
            engine.dispose()
        relational.db_path, relational.engine, relational._session_map = (
            saved_relational
        )
        relational.session_factory.configure(bind=relational.engine)
        content.content_path, content.content_database_engine = saved_content
        (
            persistence_config.base_path,
            persistence_config.provenance_path,
            persistence_config.should_mock,
            persistence_config.content_engine,
        ) = saved_config
