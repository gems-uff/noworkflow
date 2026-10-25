# Copyright (c) 2026 Universidade Federal Fluminense (UFF)
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""``now run --external-tracer strace`` as a process, and ``now restore``
of what it records (#206)

The script starts a child whose command line names only its own script;
the child reads ``hidden_in.txt``, appends to ``existing.txt`` and
creates ``hidden_out.txt``. Under the strace backend the three are file
accesses of the launch: the read with the same content before and after,
the new file written with no content before, and the file that existed
with mode ``r+`` and no content before, since its content was gone when
the log named it. ``now restore`` must not take that missing content for
a file that did not exist: the whole-trial restore leaves it in place,
says so on stderr and exits with 1, while it still removes the file the
trial created; ``-f`` without ``-i`` restores the content the trial
recorded after the change.

Linux with a strace that can trace only (``helpers/strace.py``): skips
elsewhere, fails instead under ``NOW_STRACE=require``, which the Linux
legs of CI set. The fallback where strace cannot trace is in
``test_run.py``.
"""

import pytest

from ..helpers.strace import require_strace
from .harness import sha1

SCRIPT = """\
import subprocess
import sys
result = subprocess.run([sys.executable, "child_hidden.py"], timeout=60)
print(result.returncode)
"""
CHILD = """\
with open("hidden_in.txt", encoding="utf-8") as source:
    data = source.read()
with open("existing.txt", "a", encoding="utf-8", newline="\\n") as existing:
    existing.write("more\\n")
with open("hidden_out.txt", "w", encoding="utf-8", newline="\\n") as target:
    target.write("hidden:" + data)
"""


@pytest.fixture
def traced(project):
    """The project after one ``now run --external-tracer strace``"""
    require_strace()
    project.write("script.py", SCRIPT)
    project.write("child_hidden.py", CHILD)
    project.write("hidden_in.txt", "input\n")
    project.write("existing.txt", "existing\n")
    result = project.run("run", "--external-tracer", "strace", "script.py")
    assert result.stdout == "0\n"
    return project


def accesses(project):
    """``{name: (mode, content before, content after)}`` of the trial"""
    (trial,) = project.trials()
    rows = project.query(
        "SELECT name, mode, content_hash_before, content_hash_after "
        "FROM file_access WHERE trial_id = ? ORDER BY id",
        trial["id"],
    )
    found = {}
    for row in rows:
        assert row["name"] not in found, "two accesses to {}".format(row["name"])
        found[row["name"]] = (
            row["mode"],
            row["content_hash_before"],
            row["content_hash_after"],
        )
    return found


def test_strace_records_the_files_a_child_names_nowhere(traced):
    """The child's script, named, and the three files it names nowhere;
    no warning, and no log left in the temporary directory"""
    assert accesses(traced) == {
        "child_hidden.py": (
            "r",
            sha1(CHILD.encode("utf-8")),
            sha1(CHILD.encode("utf-8")),
        ),
        "hidden_in.txt": ("r", sha1(b"input\n"), sha1(b"input\n")),
        "existing.txt": ("r+", None, sha1(b"existing\nmore\n")),
        "hidden_out.txt": ("w", None, sha1(b"hidden:input\n")),
    }
    assert [path.name for path in traced.tmp.iterdir()] == []


def test_restore_leaves_a_file_a_process_changed_without_naming_it(traced):
    """The whole-trial restore: the file whose content before was not
    recorded is left as it is, with a message and status 1, instead of
    being deleted as a file the trial created; the file the trial did
    create is removed, the read is put back"""
    (traced.path / "hidden_in.txt").write_text("changed\n", encoding="utf-8")
    (trial,) = traced.trials()
    result = traced.run("restore", trial["id"], expect=1, allow_stderr=True)
    assert (traced.path / "existing.txt").read_bytes() == b"existing\nmore\n"
    assert "existing.txt" in result.stderr
    assert "its content before was not recorded: left as it is" in result.stderr
    assert not (traced.path / "hidden_out.txt").exists()
    assert (traced.path / "hidden_in.txt").read_bytes() == b"input\n"


def test_restore_f_of_that_file_gives_its_first_recorded_content(traced):
    """``-f`` without ``-i``: the first content the trial has of the
    file, the one after the change"""
    (traced.path / "existing.txt").write_text("edited\n", encoding="utf-8")
    (trial,) = traced.trials()
    traced.run("restore", trial["id"], "-f", "existing.txt")
    assert (traced.path / "existing.txt").read_bytes() == b"existing\nmore\n"
