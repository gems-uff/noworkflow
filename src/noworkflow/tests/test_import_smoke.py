# Copyright (c) 2026 Universidade Federal Fluminense (UFF)
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""The Jupyter side of noWorkflow imports, and what the wheel ships of it

Nothing else in the suite imports the IPython magics
(``noworkflow.now.ipython.magics``) or the kernel (``noworkflow.kernel``,
which ``now kernel`` installs as ``python -m noworkflow.kernel``), so an
upgrade of IPython, ipykernel or traitlets that breaks an import would show
only in a notebook. These tests import them and check the classes they
build on; they neither start a kernel nor run a magic.

``pyproject.toml`` sets ``namespaces = false``, so setuptools puts in the
wheel only the directories that have an ``__init__.py``. ``kernel/`` had
none: from the checkout it imported as a namespace package, while the
wheel left it out and the kernelspec that ``now kernel`` installs from a
``pip install`` named a module that was not there (#341). The discovery
is checked with setuptools itself, with the options read from
``pyproject.toml``; it is plain directory listing, the same on every
system and Python version. The kernel itself is started in
``e2e/test_kernel.py``, which the ``checks`` job of ``ci.yml`` also runs
against the built wheel.
"""

import importlib
import importlib.util
import tomllib
from pathlib import Path

import pytest
import setuptools

KERNEL_MODULES = ("nowkernel", "shell", "__main__")
# Directories of the package whose scripts are data, not modules: the
# demos and the scripts that the tests trace.
DATA_DIRECTORIES = ("resources", "tests")


def find_options(root):
    """``[tool.setuptools.packages.find]`` of ``pyproject.toml``"""
    with open(root / "pyproject.toml", "rb") as handle:
        return tomllib.load(handle)["tool"]["setuptools"]["packages"]["find"]


def discovered_packages(root):
    """The packages that setuptools builds the wheel from"""
    options = find_options(root)
    finder = (
        setuptools.find_namespace_packages
        if options.get("namespaces", True)
        else setuptools.find_packages
    )
    packages = set()
    for where in options.get("where", ["."]):
        packages.update(
            finder(
                where=str(root / where),
                include=options.get("include", ("*",)),
                exclude=options.get("exclude", ()),
            )
        )
    return packages


def module_directories(package_dir):
    """Dotted names of the directories under ``package_dir`` that hold
    ``.py`` files, the data directories left out"""
    names = set()
    for path in package_dir.rglob("*.py"):
        parts = path.parent.relative_to(package_dir).parts
        if parts and parts[0] not in DATA_DIRECTORIES:
            names.add(".".join((package_dir.name,) + parts))
    return names


@pytest.fixture
def root(request):
    """The checkout, or skip outside one"""
    rootpath = request.config.rootpath
    if (
        not (rootpath / "pyproject.toml").is_file()
        or not (rootpath / "src" / "noworkflow").is_dir()
    ):
        pytest.skip("not a checkout of noWorkflow")
    return rootpath


def test_ipython_magics_import():
    """The IPython magics import, and their classes are IPython magics and
    noWorkflow's magic commands, one per ``now_*.py`` module of the package,
    each under its own name
    """
    from IPython.core.magic import Magics

    magics = importlib.import_module("noworkflow.now.ipython.magics")
    command = importlib.import_module("noworkflow.now.ipython.magics.command")
    assert issubclass(magics.NoworkflowMagics, Magics)
    assert callable(magics.register_magics)
    assert [
        name
        for name, _, cls in magics.MAGICS
        if not issubclass(cls, command.IpythonCommandMagic)
    ] == []
    modules = sorted(
        path.stem for path in Path(magics.__file__).parent.glob("now_*.py")
    )
    assert (
        sorted(cls.__module__.rsplit(".", 1)[1] for _, _, cls in magics.MAGICS)
        == modules
    )
    names = [name for name, _, _ in magics.MAGICS]
    assert len(set(names)) == len(names)


@pytest.mark.parametrize("name", KERNEL_MODULES)
def test_kernel_modules_import(name):
    """Each module of the kernel imports, its kernel is an ipykernel
    kernel, and importing ``__main__`` starts nothing
    """
    from ipykernel.ipkernel import IPythonKernel

    module = importlib.import_module("noworkflow.kernel." + name)
    nowkernel = importlib.import_module("noworkflow.kernel.nowkernel")
    assert issubclass(nowkernel.NowKernel, IPythonKernel)
    if name == "__main__":
        # The launch is guarded by __name__, which an import never sets
        # to "__main__".
        assert module.__name__ == "noworkflow.kernel.__main__"
        assert module.NowKernel is nowkernel.NowKernel


def test_kernel_is_a_regular_package():
    """``noworkflow.kernel`` is a regular package, the same from the
    checkout as from the wheel, and ``python -m noworkflow.kernel`` finds
    its ``__main__``
    """
    kernel = importlib.import_module("noworkflow.kernel")
    assert kernel.__file__ is not None
    assert importlib.util.find_spec("noworkflow.kernel.__main__") is not None


def test_package_discovery_finds_every_directory_of_modules(root):
    """setuptools, with the options of ``pyproject.toml``, finds every
    directory of modules, ``noworkflow.kernel`` included, so the wheel
    ships the module that the kernelspec of ``now kernel`` runs (#341)
    """
    packages = discovered_packages(root)
    # Not vacuous: the discovery found the package itself.
    assert {"noworkflow", "noworkflow.now", "noworkflow.tests"} <= packages
    assert "noworkflow.kernel" in packages
    left_out = module_directories(root / "src" / "noworkflow") - packages
    assert sorted(left_out) == []
