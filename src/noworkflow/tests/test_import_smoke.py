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

``noworkflow.kernel`` has no ``__init__.py``: from the checkout it imports
as a namespace package, but ``pyproject.toml`` sets ``namespaces = false``,
so setuptools leaves it out of the wheel, and the kernelspec that ``now
kernel`` installs from a ``pip install`` names a module that is not there
(#341). The discovery is checked with setuptools
itself, with the options read from ``pyproject.toml``; it is plain
directory listing, the same on every system and Python version (measured
on macOS with 3.11 to 3.15).
"""
import importlib
import importlib.util
import tomllib
from pathlib import Path

import pytest
import setuptools

import noworkflow
from noworkflow.tests.helpers.defects import Defect, known_defects

SRC = Path(noworkflow.__file__).resolve().parent.parent
KERNEL_MODULES = ("nowkernel", "shell", "__main__")
# Directories of the package whose scripts are data, not modules: the
# demos and the scripts that the tests trace.
DATA_DIRECTORIES = ("resources", "tests")

KERNEL_NOT_SHIPPED = Defect(
    reason="#341: src/noworkflow/kernel has no "
           "__init__.py and pyproject.toml sets namespaces = false, so the "
           "wheel lacks the module that the kernelspec of `now kernel` runs "
           "(python -m noworkflow.kernel: No module named noworkflow.kernel)",
    signature="noworkflow.kernel is not among the packages",
)


def find_options(root):
    """``[tool.setuptools.packages.find]`` of ``pyproject.toml``"""
    with open(root / "pyproject.toml", "rb") as handle:
        return tomllib.load(handle)["tool"]["setuptools"]["packages"]["find"]


def discovered_packages(root):
    """The packages that setuptools builds the wheel from"""
    options = find_options(root)
    finder = (setuptools.find_namespace_packages
              if options.get("namespaces", True)
              else setuptools.find_packages)
    packages = set()
    for where in options.get("where", ["."]):
        packages.update(finder(
            where=str(root / where),
            include=options.get("include", ("*",)),
            exclude=options.get("exclude", ())))
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
    if not (rootpath / "pyproject.toml").is_file() or not (
            rootpath / "src" / "noworkflow").is_dir():
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
    assert [name for name, _, cls in magics.MAGICS
            if not issubclass(cls, command.IpythonCommandMagic)] == []
    modules = sorted(path.stem for path
                     in Path(magics.__file__).parent.glob("now_*.py"))
    assert sorted(cls.__module__.rsplit(".", 1)[1]
                  for _, _, cls in magics.MAGICS) == modules
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


def test_kernel_runs_as_a_namespace_package_from_the_checkout():
    """From the checkout, ``noworkflow.kernel`` is a namespace package and
    ``python -m noworkflow.kernel`` finds its ``__main__``

    Part of the characterization of #341: a fix
    that adds ``kernel/__init__.py`` turns it into a regular package.
    """
    kernel = importlib.import_module("noworkflow.kernel")
    assert getattr(kernel, "__file__", None) is None
    assert not (SRC / "noworkflow" / "kernel" / "__init__.py").exists()
    assert importlib.util.find_spec("noworkflow.kernel.__main__") is not None


def test_package_discovery_of_the_kernel(root):
    """setuptools, with the options of ``pyproject.toml``, finds every
    directory of modules but ``noworkflow.kernel``, although
    ``kernel/__main__.py`` exists, and no package data covers it

    Characterization of #341.
    """
    packages = discovered_packages(root)
    # Not vacuous: the discovery found the package itself.
    assert {"noworkflow", "noworkflow.now", "noworkflow.tests"} <= packages
    assert (root / "src" / "noworkflow" / "kernel" / "__main__.py").is_file()
    assert "noworkflow.kernel" not in packages
    left_out = module_directories(root / "src" / "noworkflow") - packages
    assert sorted(left_out) == ["noworkflow.kernel"]
    with open(root / "pyproject.toml", "rb") as handle:
        data = tomllib.load(handle)["tool"]["setuptools"]["package-data"]
    assert [pattern for pattern in data.get("noworkflow", [])
            if pattern.startswith("kernel")] == []


@known_defects(KERNEL_NOT_SHIPPED)
def test_package_discovery_of_the_kernel_desired(root):
    """setuptools finds ``noworkflow.kernel``, so the wheel ships the
    module that the kernelspec of ``now kernel`` runs
    """
    packages = discovered_packages(root)
    assert "noworkflow.kernel" in packages, (
        "noworkflow.kernel is not among the packages that setuptools "
        "finds: {}".format(sorted(packages)))
