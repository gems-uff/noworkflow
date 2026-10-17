# Copyright (c) 2026 Universidade Federal Fluminense (UFF)
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""``Deployment.get_version``: the version a ``module`` row records

``now run`` calls ``get_version`` for every module the script imports for
the first time (the loaders of ``prov_deployment/py3module.py``), and ``now
restore`` for the local modules of its backup trial. It looks first for an
installed distribution named after the module, through
``importlib.metadata``, and falls back to the module's own ``__version__``,
``version``, ``__VERSION__`` or ``VERSION``.

Each test puts a distribution's metadata directory in ``tmp_path``, puts
``tmp_path`` on ``sys.path`` and asks for the version of a module object
that declares ``__version__ = "9.9"``, so the result says which of the two
sources won.

What changed with the move from ``pkg_resources`` to ``importlib.metadata``
(PR #186) and what did not:

- ``importlib.metadata`` reads ``sys.path`` at each call. ``pkg_resources``
  read it once, when ``now`` imported it at startup, and missed a
  distribution under an entry added later: a directory the script puts on
  ``sys.path``, or, under the ``now`` console script, the script's own
  directory, which ``now run`` puts at ``sys.path[0]`` after that.
- The names still compare as ``pkg_resources`` compared them: dots stay
  apart from ``-`` and ``_``.
- A distribution whose metadata names no version still leaves the module's
  own version, on every Python.
"""

import types
from unittest import mock

import pytest

from noworkflow.now.collection.prov_deployment.deployment import Deployment

MODULE_VERSION = "9.9"


class Metascript(object):
    """What ``Deployment`` keeps a weak proxy of; ``get_version`` reads
    nothing from it"""


@pytest.fixture
def get_version(tmp_path, monkeypatch):
    """``get_version`` of a module named ``name`` that declares
    ``MODULE_VERSION``, with ``tmp_path`` first on ``sys.path``"""
    monkeypatch.syspath_prepend(str(tmp_path))
    metascript = Metascript()
    deployment = Deployment(metascript)

    def version_of(name):
        module = types.ModuleType(name)
        module.__version__ = MODULE_VERSION
        return deployment.get_version(module)

    # yield, not return: metascript, behind a weak proxy, outlives the test
    yield version_of


def distribution(root, directory, metadata=None):
    """A metadata directory under root, with METADATA when given"""
    path = root / directory
    path.mkdir()
    if metadata is not None:
        (path / "METADATA").write_text(metadata, encoding="utf-8")


def test_a_module_named_after_a_distribution_records_its_version(
        get_version, tmp_path):
    """The distribution's version wins over the module's ``__version__``,
    also when its directory joined ``sys.path`` after noWorkflow started
    (``tmp_path``, here)"""
    distribution(tmp_path, "helper-1.2.3.dist-info",
                 "Metadata-Version: 2.1\nName: helper\nVersion: 1.2.3\n")
    assert get_version("helper") == "1.2.3"


def test_a_module_without_a_distribution_records_its_own_version(
        get_version, tmp_path):
    """No distribution has the module's name: ``__version__`` is recorded"""
    distribution(tmp_path, "other-1.2.3.dist-info",
                 "Metadata-Version: 2.1\nName: other\nVersion: 1.2.3\n")
    assert get_version("helper") == MODULE_VERSION


def test_a_dotted_module_does_not_take_the_version_of_a_dashed_distribution(
        get_version, tmp_path):
    """``ns.sub`` is not the distribution ``ns-sub``

    PEP 503 folds ``.`` into ``-``, and ``importlib.metadata`` finds
    ``ns-sub`` for ``ns.sub``: Flask's own submodule ``flask.json`` would
    get the version of the plugin Flask-JSON. ``pkg_resources`` kept the
    dots apart, and so does ``get_version``.
    """
    distribution(tmp_path, "ns_sub-3.0.dist-info",
                 "Metadata-Version: 2.1\nName: ns-sub\nVersion: 3.0\n")
    assert get_version("ns.sub") == MODULE_VERSION


def test_a_dotted_module_matches_a_distribution_with_the_same_dots(
        get_version, tmp_path):
    """``ns.sub`` is the distribution ``ns.sub``, as ``zope.interface`` is
    the distribution that ships the module ``zope.interface``"""
    distribution(tmp_path, "ns_sub-3.0.dist-info",
                 "Metadata-Version: 2.1\nName: ns.sub\nVersion: 3.0\n")
    assert get_version("ns.sub") == "3.0"


@pytest.mark.parametrize("metadata", [
    pytest.param(None, id="no METADATA"),
    pytest.param("Metadata-Version: 2.1\nName: helper\n", id="no Version"),
    pytest.param("Metadata-Version: 2.1\nName: helper\nVersion:\n",
                 id="empty Version"),
])
def test_a_distribution_without_a_version_leaves_the_module_version(
        get_version, tmp_path, metadata):
    """Metadata that names no version is not a version

    A leftover ``helper-1.0.dist-info`` with no ``METADATA``, or a
    ``METADATA`` without ``Version``, makes ``importlib.metadata.version``
    return None on Python 3.11 to 3.14 (with a DeprecationWarning from
    3.12) and raise from 3.15 on; an empty ``Version:`` gives ``""`` on
    every version. The module's own ``__version__`` is recorded instead.
    """
    distribution(tmp_path, "helper-1.0.dist-info", metadata)
    assert get_version("helper") == MODULE_VERSION


def test_a_script_that_patches_importlib_metadata_does_not_reach_the_lookup(
        get_version, tmp_path):
    """A traced test suite that patches ``importlib.metadata`` while it
    imports a module for the first time does not change what is recorded

    ``get_version`` runs inside the script's process, from the import
    finder. With ``importlib.metadata.version`` looked up at each call, a
    ``mock.patch`` of it put its return value in the ``module`` row, and a
    bare ``MagicMock`` made ``now run`` fail when it stored the trial.
    """
    distribution(tmp_path, "helper-1.2.3.dist-info",
                 "Metadata-Version: 2.1\nName: helper\nVersion: 1.2.3\n")
    with mock.patch("importlib.metadata.version",
                    return_value="0.0-fake") as version, \
            mock.patch("importlib.metadata.distribution",
                       return_value=None) as find:
        recorded = get_version("helper")
    assert (recorded, version.called, find.called) == ("1.2.3", False, False)
