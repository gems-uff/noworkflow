# Copyright (c) 2026 Universidade Federal Fluminense (UFF)
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""``connected_to`` and ``connected_two_trials``: in-process code on a real store

The patterns and the vis views read through the persistence layer that the
suite connects to in-memory stores on import. These tests pin what the
tests built on the fixture rely on: while connected, the models read the
real store (rows checked against SQL on its ``db.sqlite``) and the content
engine reads its content directory; afterwards the in-memory stores are the
same objects, holding the same rows.
"""

import pytest

from noworkflow.now.persistence import content, persistence_config, relational
from noworkflow.now.persistence.models import FileAccess, Trial
from noworkflow.tests.helpers import models
from noworkflow.tests.helpers.persistence import connected_to


def in_memory_state():
    return (
        relational.engine,
        relational._session_map,
        relational.db_path,
        content.content_database_engine,
        persistence_config.should_mock,
        persistence_config.base_path,
    )


def test_connected_two_trials_reads_the_trials_of_the_real_store(connected_two_trials):
    """The models list the trials that SQL finds in the store's file"""
    expected = [row["id"] for row in connected_two_trials.trials()]
    assert len(expected) == 2
    found = [
        trial.id
        for trial in relational.session.query(Trial.m).order_by(Trial.m.sequence_key)
    ]
    assert found == expected


def test_connected_two_trials_reads_the_content_of_the_real_store(connected_two_trials):
    """``content.get`` returns the bytes the store holds under a hash"""
    rows = connected_two_trials.query(
        "SELECT content_hash_before FROM file_access "
        "WHERE name LIKE '%data1.dat' AND content_hash_before IS NOT NULL "
        "LIMIT 1"
    )
    assert rows, "the weather trials record no content of data1.dat"
    content_hash = rows[0]["content_hash_before"]
    assert content.get(content_hash) == connected_two_trials.content(content_hash)
    accesses = (
        relational.session.query(FileAccess.m)
        .filter(FileAccess.m.content_hash_before == content_hash)
        .count()
    )
    assert accesses >= 1


def test_connected_to_brings_back_the_in_memory_stores(two_trial_project):
    """After the block, the in-memory rows and objects are the ones before

    Control: a trial created in memory is invisible while connected.
    """
    models.erase_database()
    trial_id = Trial.create(**models.trial_params(script="memory.py"))
    before = in_memory_state()
    with connected_to(two_trial_project.path):
        assert in_memory_state() != before
        scripts = {trial.script for trial in relational.session.query(Trial.m)}
        assert "memory.py" not in scripts
    assert in_memory_state() == before
    assert [trial.id for trial in relational.session.query(Trial.m)] == [trial_id]
    assert content.get(content.put(b"in memory")) == b"in memory"
    models.erase_database()


def test_connected_to_a_directory_without_a_store_refuses(tmp_path):
    """No store: FileNotFoundError, and the in-memory stores stay"""
    before = in_memory_state()
    with pytest.raises(FileNotFoundError):
        with connected_to(tmp_path):
            pass  # pragma: no cover
    assert in_memory_state() == before
