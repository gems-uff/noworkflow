# Copyright (c) 2026 Universidade Federal Fluminense (UFF)
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""Fixtures of the content engine tests: an isolated git and a store

``isolated_git`` gives every test a git that sees nothing of the machine:
the inherited ``GIT_*`` variables are deleted (a ``GIT_DIR`` or a
``GIT_INDEX_FILE`` exported by a git hook would make the puregit engine
rewrite another repository), the global configuration is an empty file of
the test's own and the system one is ignored, repository discovery stops
at ``tmp_path``, ``HOME`` is a directory in ``tmp_path`` (the git engines
read it when they are built), and every commit gets the synthetic identity
and a fixed date. Without the identity, a commit records the user's real
name and address on macOS and fails on a Linux machine without one.

``engine`` connects a store of the engine ``engine_spec`` names (one per
entry of ``engines.ENGINES``) in ``project_dir``, through the product's
route, and closes it afterwards.
"""
import dataclasses
import os
from pathlib import Path

import pytest

from .engines import COMMIT_DATE, ENGINES, IDENTITY_EMAIL, IDENTITY_NAME, open_store


@dataclasses.dataclass
class GitEnvironment:
    """Where the isolated git of a test lives"""

    root: Path
    home: Path
    global_config: Path

    def configure(self, text):
        """Replace the test's global git configuration"""
        self.global_config.write_text(text, encoding="utf-8")


@pytest.fixture
def isolated_git(tmp_path, monkeypatch):
    """A git environment that reads nothing of the machine's, in tmp_path"""
    for key in list(os.environ):
        if key.startswith("GIT_"):
            monkeypatch.delenv(key)
    # git reads EMAIL before guessing an address from the machine.
    monkeypatch.delenv("EMAIL", raising=False)
    home = tmp_path / "home"
    home.mkdir()
    global_config = tmp_path / "gitconfig"
    global_config.write_text("", encoding="utf-8")
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("USERPROFILE", str(home))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(home / ".config"))
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(global_config))
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")
    monkeypatch.setenv("GIT_CEILING_DIRECTORIES", str(tmp_path))
    for role in ("AUTHOR", "COMMITTER"):
        monkeypatch.setenv("GIT_{}_NAME".format(role), IDENTITY_NAME)
        monkeypatch.setenv("GIT_{}_EMAIL".format(role), IDENTITY_EMAIL)
        monkeypatch.setenv("GIT_{}_DATE".format(role), COMMIT_DATE)
    return GitEnvironment(tmp_path, home, global_config)


@pytest.fixture(params=ENGINES, ids=str)
def engine_spec(request):
    """One of ``engines.ENGINES``, skipped where it cannot run"""
    spec = request.param
    spec.skip_if_unavailable()
    return spec


@pytest.fixture
def project_dir(isolated_git):
    """An empty project directory, ``tmp_path/project``"""
    path = isolated_git.root / "project"
    path.mkdir()
    return path


@pytest.fixture
def engine(engine_spec, project_dir):
    """The content engine of a new store of ``engine_spec`` in project_dir"""
    database = open_store(project_dir, engine_spec.name)
    yield database.content_database_engine
    database.content_database_engine.close()
