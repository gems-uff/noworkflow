# Copyright (c) 2016 Universidade Federal Fluminense (UFF)
# Copyright (c) 2016 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""Deployment provenance collector"""
from __future__ import (absolute_import, print_function,
                        division, unicode_literals)

import importlib
import modulefinder
import os
import platform
import socket
import sys
import weakref
import getpass
import pkg_resources

from future.utils import viewitems, native_str
from future.builtins import map as cvmap

from ...persistence.models import Module
from ...persistence import content
from ...utils.io import print_msg, redirect_output
from ...utils.metaprofiler import meta_profiler
from ...utils.cross_version import string
from ...utils.functions import version


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

    def add_module(self, name, version, path, code_id, transformed=False):
        """Insert module into provenance store"""
        self.metascript.modules_store.add(
            self.metascript.trial_id, name, version, path, code_id, transformed
        )

    def get_version(self, module):
        """Get module version"""
        module_name = module.__name__
        if module_name in sys.builtin_module_names:
            return platform.python_version()

        # Check package declared module version
        try:
            # ToDo: This is slow! Is there any alternative?
            return pkg_resources.get_distribution(module_name).version
        except Exception:                                                        # pylint: disable=broad-except
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
        except Exception:                                                        # pylint: disable=broad-except
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
