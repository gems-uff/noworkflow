# Copyright (c) 2026 Universidade Federal Fluminense (UFF)
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""``utils/functions.py``: the files ``noworkflow/resources`` ships

``version`` reads ``version.txt`` (``now --version``, the ``version`` of
every trial), ``trial_prolog.py`` reads ``rules.pl`` (``now export prolog
-r``), and ``now demo`` lists the demos, reads each one's ``steps.txt`` and
copies its files with ``recursive_copy``. They read through
``importlib.resources`` (#225); a name is relative to the ``noworkflow``
package, and ``now demo`` builds it with ``os.path.join``, so a ``\\``
separates its parts as well as a ``/``.

The expected values come from the files of the checkout, which is where the
suite imports ``noworkflow`` from.
"""
import filecmp
import os
import warnings
from pathlib import Path

import noworkflow
from noworkflow.now.utils.functions import (
    recursive_copy,
    resource,
    resource_is_dir,
    resource_ls,
    version,
)

RESOURCES = Path(noworkflow.__file__).resolve().parent / "resources"


def test_version_is_the_text_of_version_txt_without_a_warning():
    """``version`` strips ``version.txt``; reading it warns about nothing
    (``pkg_resources`` warned about the ``..`` its old name held)"""
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        found = version()
    expected = (RESOURCES / "version.txt").read_text(encoding="utf-8").strip()
    assert found == expected


def test_resource_reads_bytes_and_decodes_on_request():
    """``resource`` gives the bytes of the file, or its text when an
    encoding is named"""
    path = RESOURCES / "rules.pl"
    assert resource("resources/rules.pl") == path.read_bytes()
    assert resource("resources/rules.pl", "UTF-8") == path.read_text(
        encoding="utf-8")


def test_resource_takes_a_name_joined_with_either_separator():
    """A name built with ``os.path.join`` on Windows names the same file"""
    expected = (RESOURCES / "demo" / "1" / "steps.txt").read_bytes()
    assert resource("resources\\demo\\1\\steps.txt") == expected
    assert resource(os.path.join("resources", "demo", "1",
                                 "steps.txt")) == expected


def test_resource_ls_lists_the_entries_of_a_directory():
    """``resource_ls`` gives the names in a directory, as the choices of
    ``now demo`` need them"""
    assert sorted(resource_ls("resources/demo")) == sorted(
        os.listdir(RESOURCES / "demo"))


def test_resource_is_dir_tells_directories_from_files_and_absences():
    """A directory is one, a file and a missing name are not"""
    assert resource_is_dir("resources/demo")
    assert not resource_is_dir("resources/version.txt")
    assert not resource_is_dir("resources/no-such-entry")


def test_recursive_copy_copies_a_demo_byte_for_byte(tmp_path):
    """``recursive_copy`` reproduces a demo's tree, as the ``>LOAD`` step of
    ``now demo`` does"""
    source = RESOURCES / "demo" / "1"
    target = tmp_path / "demo_1"
    recursive_copy("resources/demo/1", str(target))

    def tree(root):
        return sorted(path.relative_to(root).as_posix()
                      for path in root.rglob("*") if path.is_file())

    assert tree(target) == tree(source)
    _, mismatch, errors = filecmp.cmpfiles(
        source, target, tree(source), shallow=False)
    assert (mismatch, errors) == ([], [])
