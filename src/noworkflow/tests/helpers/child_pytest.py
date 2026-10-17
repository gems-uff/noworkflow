# Copyright (c) 2026 Universidade Federal Fluminense (UFF)
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""A child pytest under a copy of the root ``conftest.py``

For the tests of what the root conftest does around every test (the leak
detector, the mask of the hostname in reports): the only way to see a
hook act on a test is to run that test in another pytest, whose process
state the parent does not share.
"""
import os
import subprocess
import sys

import pytest

from ..e2e.harness import clean_env, tail

CHILD_FILES = ["conftest.py", "pytest.ini", "test_child.py"]


def run_child_pytest(request, tmp_path, source, mode="fail", args=()):
    """Run ``source`` as test_child.py under a copy of the root conftest.py

    A child pytest in ``tmp_path``, with the harness's synthetic environment
    and ``NOW_LEAK_CHECK=mode``, plus ``args`` on its command line: its
    conftest runs the session from a scratch directory under the child's
    TMPDIR, no bytecode and no cache are written, and the parent's process
    state is not shared. Returns the completed process; asserts that the
    suite directory holds only the files written here.
    """
    conftest = request.config.rootpath / "conftest.py"
    if not conftest.is_file():
        pytest.skip("conftest.py is not here: the suite runs outside the "
                    "checkout")
    suite, home, tmp = (tmp_path / "suite", tmp_path / "home",
                        tmp_path / "tmp")
    for directory in (suite, home, tmp):
        directory.mkdir()
    (suite / "conftest.py").write_bytes(conftest.read_bytes())
    # Anchors the child's rootdir here, away from any configuration above.
    (suite / "pytest.ini").write_text("[pytest]\n", encoding="utf-8")
    (suite / "test_child.py").write_text(source, encoding="utf-8")
    env = clean_env(home, tmp, [sys.executable])
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["NOW_LEAK_CHECK"] = mode
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "-p", "no:cacheprovider",
         "-p", "no:warnings", "-q"] + list(args) + ["suite"],
        cwd=str(tmp_path),
        env=env,
        stdin=subprocess.DEVNULL,
        capture_output=True,
        encoding="utf-8",
        errors="replace",
        timeout=120,
    )
    left = sorted(os.listdir(suite))
    assert left == CHILD_FILES, (
        "the child pytest wrote into its suite directory: {}\n{}".format(
            left, child_report(result)))
    return result


def child_report(result):
    """A child pytest's outcome, for assertion messages"""
    return "return code {}\n--- stdout ---\n{}\n--- stderr ---\n{}".format(
        result.returncode, tail(result.stdout), tail(result.stderr))
