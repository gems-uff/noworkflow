# Copyright (c) 2026 Universidade Federal Fluminense (UFF)
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""Report every path pytest would collect under the e2e corpus (pytest plugin)

``test_premises`` starts a child ``pytest --collect-only`` with
``-p noworkflow.tests.premises.corpus_spy``. The spy wraps
``pytest_ignore_collect``: when every other plugin, the root conftest's
``collect_ignore_glob`` included, has decided not to ignore a path inside
the corpus, the spy records it and ignores it itself. The premise has
already fallen by then, and ignoring the path keeps the child from
importing the script (a corpus script that calls ``sys.exit`` at import
would crash the collection before any report). ``pytest_collect_file`` and
the collected items are watched as well, for paths that skip the ignore
hook (the paths given on the command line).

At the end of the session the plugin writes, in the terminal summary, one
``CORPUS-SPY reached <path>`` line per corpus path or item it saw and a
final ``CORPUS-SPY done files=<n> e2e=<n> corpus=<n>`` line. ``e2e`` counts
the files collected next to the corpus (``harness.py``, ``golden.py``...):
when it is zero, the walk never reached the corpus's parent directory, and
an empty report proves nothing.

Paths are recognized by their components, not by the location of this
module, so the spy also works when the installed ``noworkflow`` is not the
checkout that pytest walks. The file is not named ``test_*.py``: pytest
never loads it as a test module, and the doctest import of it registers no
hook.
"""
from pathlib import PurePath

import pytest

MARKER = "CORPUS-SPY"
E2E_PARTS = ("noworkflow", "tests", "e2e")
CORPUS_PARTS = E2E_PARTS + ("corpus",)

_SEEN = {"files": 0, "e2e": 0, "corpus": []}


def _below(path, parts):
    """Whether ``path`` has ``parts`` as consecutive components, and more

    The comparison is exact: the directories of the package are lowercase
    on every system, and pytest reports paths with the case on disk.
    """
    # A PurePath keeps its own flavour: a Windows path stays one on POSIX.
    path = path if isinstance(path, PurePath) else PurePath(path)
    components = path.parts
    size = len(parts)
    return any(
        components[index:index + size] == parts
        for index in range(len(components) - size)
    )


def is_corpus_path(path):
    """Whether ``path`` is a file or directory inside the e2e corpus"""
    return _below(path, CORPUS_PARTS)


def is_e2e_path(path):
    """Whether ``path`` is inside the e2e package but outside the corpus"""
    return _below(path, E2E_PARTS) and not is_corpus_path(path)


def _relative(path, config):
    try:
        return PurePath(path).relative_to(config.rootpath).as_posix()
    except ValueError:
        return PurePath(path).as_posix()


def pytest_sessionstart(session):
    _SEEN.update(files=0, e2e=0, corpus=[])


@pytest.hookimpl(wrapper=True)
def pytest_ignore_collect(collection_path, config):
    ignored = yield
    if ignored or not is_corpus_path(collection_path):
        return ignored
    _SEEN["corpus"].append(_relative(collection_path, config))
    return True


def pytest_collect_file(file_path, parent):
    _SEEN["files"] += 1
    if is_corpus_path(file_path):
        _SEEN["corpus"].append(_relative(file_path, parent.config))
    elif is_e2e_path(file_path):
        _SEEN["e2e"] += 1


def pytest_collection_modifyitems(session, config, items):
    for item in items:
        path = getattr(item, "path", None)
        if path is not None and is_corpus_path(path):
            _SEEN["corpus"].append("item " + item.nodeid)


def pytest_terminal_summary(terminalreporter):
    for path in _SEEN["corpus"]:
        terminalreporter.write_line("{} reached {}".format(MARKER, path))
    terminalreporter.write_line("{} done files={} e2e={} corpus={}".format(
        MARKER, _SEEN["files"], _SEEN["e2e"], len(_SEEN["corpus"])))
