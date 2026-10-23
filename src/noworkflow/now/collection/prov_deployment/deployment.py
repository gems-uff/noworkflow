# Copyright (c) 2016 Universidade Federal Fluminense (UFF)
# Copyright (c) 2016 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""Deployment provenance collector"""

from __future__ import absolute_import, division, print_function, unicode_literals

import getpass
import importlib.metadata
import os
import platform
import re
import socket
import sys
import weakref

from future.builtins import map as cvmap
from future.utils import native_str, viewitems

from ...utils.cross_version import string
from ...utils.functions import version
from ...utils.io import print_msg
from ...utils.metaprofiler import meta_profiler

# Bound when noWorkflow starts, so that a traced script that patches
# importlib.metadata (unittest.mock in a test suite) does not reach it
find_distribution = importlib.metadata.distribution


def load_metadata_modules():
    """Import, before any script, what reading a distribution's metadata
    imports (importlib.metadata._adapters, email.policy and its kin)

    get_version reads metadata from inside the import finder, while the
    script runs, and a module imported there for the first time would be
    recorded as one the script imported. Reading noWorkflow's own metadata
    takes the same path as reading any other's.
    """
    try:
        find_distribution("noworkflow").metadata
    # Not installed as a distribution: nothing to warm, and get_version
    # falls back to the attributes
    except Exception:  # pylint: disable=broad-except  # nosec B110
        pass


load_metadata_modules()


def distribution_key(name):
    """A distribution name as pkg_resources compared it: case and runs of
    "-" and "_" do not matter, dots do

    importlib.metadata also folds dots (PEP 503), so the submodule
    flask.json would find the plugin Flask-JSON.
    """
    return re.sub(r"[-_]+", "-", name).lower()


class Deployment(object):
    """Collect deployment provenance"""

    def __init__(self, metascript):
        self.metascript = weakref.proxy(metascript)

    @meta_profiler("environment")
    def _collect_environment_provenance(self):
        """Collect enviroment variables and operating system characteristics
        Return dict
        """
        attrs = self.metascript.environment_attrs_store
        trial_id = self.metascript.trial_id

        attrs.add(trial_id, "OS_NAME", platform.system())
        # Unix environment
        try:
            for name in os.sysconf_names:
                try:
                    attrs.add(trial_id, name, os.sysconf(name))
                except (ValueError, OSError):
                    pass
            for name in os.confstr_names:
                attrs.add(trial_id, name, os.confstr(name))
        except AttributeError:
            pass

        os_name, _, os_release, os_version, _, _ = platform.uname()
        attrs.add(trial_id, "OS_NAME", os_name)
        attrs.add(trial_id, "OS_RELEASE", os_release)
        attrs.add(trial_id, "OS_VERSION", os_version)

        # Both Unix and Windows
        for attr, value in viewitems(os.environ):
            attrs.add(trial_id, attr, value)

        attrs.add(trial_id, "USER", getpass.getuser())
        attrs.add(trial_id, "PWD", os.getcwd())
        attrs.add(trial_id, "PID", os.getpid())
        attrs.add(trial_id, "HOSTNAME", socket.gethostname())
        attrs.add(trial_id, "ARCH", platform.architecture()[0])
        attrs.add(trial_id, "PROCESSOR", platform.processor())
        attrs.add(trial_id, "PYTHON_IMPLEMENTATION", platform.python_implementation())
        attrs.add(trial_id, "PYTHON_VERSION", platform.python_version())

        attrs.add(trial_id, "NOWORKFLOW_VERSION", version())

    def add_module(
        self, name, version, path, code_id, transformed=False, fullpath=None
    ):
        """Insert module into provenance store; returns its id"""
        return self.metascript.modules_store.add(
            self.metascript.trial_id,
            name,
            version,
            path,
            code_id,
            transformed,
            fullpath,
        )

    def get_version(self, module):
        """Get module version"""
        module_name = module.__name__
        if module_name in sys.builtin_module_names:
            return platform.python_version()

        # Check package declared module version
        try:
            metadata = find_distribution(module_name).metadata
            dist_name = metadata.get("Name")
            dist_version = metadata.get("Version")
            # Metadata that names no version is not a version; before 3.15
            # importlib.metadata.version returns None for it instead of raising
            if (
                isinstance(dist_name, string)
                and isinstance(dist_version, string)
                and dist_version
                and distribution_key(dist_name) == distribution_key(module_name)
            ):
                return native_str(dist_version)
        # A module name is rarely a distribution's name, and broken metadata
        # raises more than PackageNotFoundError (KeyError, UnicodeDecodeError);
        # any failure falls back to the attributes below
        except Exception:  # pylint: disable=broad-except  # nosec B110
            pass

        # Check explicitly declared module version
        try:
            for attr in ["__version__", "version", "__VERSION__", "VERSION"]:
                try:
                    module_version = getattr(module, attr)
                    if isinstance(module_version, string):
                        return native_str(module_version)
                    if isinstance(module_version, tuple):
                        return ".".join(cvmap(str, module_version))
                except AttributeError:
                    pass
        # A module whose attributes raise still gets its row, without a version
        except Exception:  # pylint: disable=broad-except  # nosec B110
            pass

        # If no other option work, return None
        return None

    @meta_profiler("deployment")
    def collect_provenance(self):
        """Collect deployment provenance:
        - environment variables

        Modules are collected during the execution

        metascript should have "trial_id" and "path"
        """
        print_msg("  registering environment attributes")
        self._collect_environment_provenance()

    def store_provenance(self):
        """Store deployment provenance"""
        metascript = self.metascript
        # Remove after save
        partial = True
        metascript.environment_attrs_store.do_store(partial)
        metascript.modules_store.do_store(partial)
