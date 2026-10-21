# Copyright (c) 2026 Universidade Federal Fluminense (UFF)
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""``now demo --steps``: a slice that creates no demo directory (#435)

``Demo.execute`` (``cmd/cmd_demo.py``) runs the steps of
``resources/demo/<id>/steps.txt`` that ``--steps`` selects. Only a
``>LOAD`` step creates the demo directory (``recursive_copy``), but a
``$now`` step changes into it before running ``now``, and the command ends
with ``os.chdir(directory)`` whatever ran. On a fresh project, a slice
without a ``>LOAD`` before its first ``$now`` step, or without any, ends in
``FileNotFoundError``. ``0:1`` is ``>ERASE_ALL`` alone, which does nothing
on a missing directory and reaches the final ``chdir``; ``2:3`` is the
first ``$now run`` of demo 1, which fails before any ``now`` starts. Neither
needs the console script nor matplotlib, so they run on every leg (the
whole demo is ``test_demo_1_through_the_console_script`` of
``test_restore.py``).
"""

import pytest

from ..helpers.defects import Defect, known_defects

SLICES = ("0:1", "2:3")

NO_DEMO_DIRECTORY = Defect(
    "#435: Demo.execute (cmd/cmd_demo.py) changes into the demo directory "
    "before a $now step and once more after the last step, and only a "
    ">LOAD step creates it, so a slice without one ends in "
    "FileNotFoundError",
    signature="Traceback (most recent call last)",
)


@pytest.mark.parametrize("steps", SLICES)
def test_demo_slice_without_load_fails_on_a_fresh_project(project, steps):
    """The slice crashes with exit status 1, a traceback that ends in
    FileNotFoundError naming the demo directory, and no directory"""
    result = project.run("demo", "1", "--steps", steps, expect=1, allow_stderr=True)

    assert result.stdout.startswith("Creating Demo 1\n"), str(result)
    last = result.stderr.strip().splitlines()[-1]
    assert last.startswith("FileNotFoundError: "), str(result)
    assert "'demo_1'" in last, str(result)
    assert not (project.path / "demo_1").exists()


@pytest.mark.parametrize("steps", SLICES)
@known_defects(NO_DEMO_DIRECTORY)
def test_demo_slice_without_load_fails_on_a_fresh_project_desired(project, steps):
    """A slice of the steps runs without a traceback on a fresh project"""
    result = project.run("demo", "1", "--steps", steps, expect=None, allow_stderr=True)

    assert "Traceback" not in result.stderr, result.stderr
