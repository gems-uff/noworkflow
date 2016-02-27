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

from future.utils import viewitems
from future.builtins import map as cvmap

from ...persistence.models import EnvironmentAttr, Module, Dependency
from ...persistence import content
from ...utils.io import print_msg, redirect_output
from ...utils.metaprofiler import meta_profiler
from ...utils.cross_version import string, default_string
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

        attrs.add("OS_NAME", platform.system())
        # Unix environment
        try:
            for name in os.sysconf_names:
                try:
                    attrs.add(name, os.sysconf(name))
                except (ValueError, OSError):
                    pass
            for name in os.confstr_names:
                attrs.add(name, os.confstr(name))
        except AttributeError:
            pass

        os_name, _, os_release, os_version, _, _ = platform.uname()
        attrs.add("OS_NAME", os_name)
        attrs.add("OS_RELEASE", os_release)
        attrs.add("OS_VERSION", os_version)

        # Both Unix and Windows
        for attr, value in viewitems(os.environ):
            attrs.add(attr, value)

        attrs.add("USER", getpass.getuser())
        attrs.add("PWD", os.getcwd())
        attrs.add("PID", os.getpid())
        attrs.add("HOSTNAME", socket.gethostname())
        attrs.add("ARCH", platform.architecture()[0])
        attrs.add("PROCESSOR", platform.processor())
        attrs.add("PYTHON_IMPLEMENTATION", platform.python_implementation())
        attrs.add("PYTHON_VERSION", platform.python_version())

        attrs.add("NOWORKFLOW_VERSION", version())

    @meta_profiler("modules")
    def _collect_modules_provenance(self):
        with redirect_output():
            modules = self._find_modules()

            print_msg("  registering provenance from {} modules".format(
                len(modules) - 1))
            self._extract_modules_provenance(modules)

    @meta_profiler("find_modules")
    def _find_modules(self):
        """Use modulefinder to find modules

        Return finder.modules dict
        """
        metascript = self.metascript
        excludes = set()
        last_name = "A" * 255  # invalid name
        max_atemps = 1000
        for i in range(max_atemps):
            try:
                finder = modulefinder.ModuleFinder(excludes=excludes)
                finder.run_script(metascript.path)
                print(metascript.path)
                return finder.modules
            except SyntaxError as exc:
                name = exc.filename.split("site-packages/")[-1]                  # pylint: disable=no-member
                name = name.replace(os.sep, ".")
                name = name[:name.rfind(".")]
                if last_name in name:
                    last_name = last_name[last_name.find(".") + 1:]
                else:
                    last_name = name
                excludes.add(last_name)
                print_msg("   skip module due syntax error: {} ({}/{})"
                          .format(last_name, i + 1, max_atemps))
        return {}

    @meta_profiler("extract_modules")
    def _extract_modules_provenance(self, python_modules):
        """Return a set of module dependencies in the form:
            (name, version, path, code_hash)
        Store module provenance in the content database
        """
        metascript = self.metascript
        modules = metascript.modules_store
        dependencies = metascript.dependencies_store
        modules.id = Module.id_seq()
        for name, module in viewitems(python_modules):
            if name != "__main__":
                module_version = self.get_version(name)
                path = module.__file__
                if path is None:
                    code_hash = None
                else:
                    with open(path, "rb") as fil:
                        code_hash = content.put(fil.read())
                info = (name, module_version, path, code_hash)
                mid = Module.fast_load_module_id(*info) or modules.add(*info)
                dependencies.add(mid)

    def get_version(self, module_name):                                         # pylint: disable=no-self-use
        """Get module version"""
        # Check built-in module
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
            module = importlib.import_module(module_name)
            for attr in ["__version__", "version", "__VERSION__", "VERSION"]:
                try:
                    module_version = getattr(module, attr)
                    if isinstance(module_version, string):
                        return default_string(module_version)
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
        - modules dependencies

        metascript should have "trial_id" and "path"
        """
        print_msg("  registering environment attributes")
        self._collect_environment_provenance()

        if self.metascript.bypass_modules:
            print_msg("  using previously detected module dependencies "
                      "(--bypass-modules).")
        else:
            print_msg("  searching for module dependencies")
            self._collect_modules_provenance()

    def store_provenance(self):
        """Store deployment provenance"""
        metascript = self.metascript
        tid = metascript.trial_id
        # Remove after save
        partial = True
        EnvironmentAttr.fast_store(tid, metascript.environment_attrs_store,
                                   partial)
        Module.fast_store(tid, metascript.modules_store, partial)
        Dependency.fast_store(tid, metascript.dependencies_store, partial)
