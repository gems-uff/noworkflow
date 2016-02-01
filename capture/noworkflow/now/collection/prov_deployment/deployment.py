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
import pkg_resources

from future.utils import viewitems

from ...persistence.models import EnvironmentAttr, Module, Dependency
from ...persistence import content
from ...utils.io import print_msg, redirect_output
from ...utils.metaprofiler import meta_profiler
from ...utils.cross_version import string, default_string
from ...utils.functions import version


class Deployment(object):

    @meta_profiler("environment")
    def _collect_environment_provenance(self, metascript):
        """Collect enviroment variables and operating system characteristics
        Return dict
        """
        attrs = metascript.environment_attrs_store

        attrs.add("OS_NAME", platform.system())
        # Unix environment
        try:
            for name in os.sysconf_names:
                try:
                    attrs.add(name, os.sysconf(name))
                except ValueError:
                    pass
            for name in os.confstr_names:
                attrs.add(name, os.confstr(name))
            attrs.add("USER", os.getlogin())
        except:
            pass

        os_name, _, os_release, os_version, _, _ = platform.uname()
        attrs.add("OS_NAME", os_name)
        attrs.add("OS_RELEASE", os_release)
        attrs.add("OS_VERSION", os_version)

        # Both Unix and Windows
        for attr, value in viewitems(os.environ):
            attrs.add(attr, value)

        attrs.add("PWD", os.getcwd())
        attrs.add("PID", os.getpid())
        attrs.add("HOSTNAME", socket.gethostname())
        attrs.add("ARCH", platform.architecture()[0])
        attrs.add("PROCESSOR", platform.processor())
        attrs.add("PYTHON_IMPLEMENTATION", platform.python_implementation())
        attrs.add("PYTHON_VERSION", platform.python_version())

        attrs.add("NOWORKFLOW_VERSION", version())

    @meta_profiler("modules")
    def _collect_modules_provenance(self, metascript):
        with redirect_output():
            modules = self._find_modules(metascript)

            print_msg("  registering provenance from {} modules".format(
                len(modules) - 1))
            self._extract_modules_provenance(metascript, modules)

    @meta_profiler("find_modules")
    def _find_modules(self, metascript):
        """Use modulefinder to find modules

        Return finder.modules
        """
        excludes = set()
        last_name = None
        max_atemps = 1000
        for i in range(max_atemps):
            try:
                finder = modulefinder.ModuleFinder(excludes=excludes)
                finder.run_script(metascript.path)
                print(metascript.path)
                return finder.modules
            except SyntaxError as e:
                name = e.filename.split("site-packages/")[-1]
                name = name.replace(os.sep, ".")
                name = name[:name.rfind(".")]
                if last_name is not None and last_name in name:
                    last_name = last_name[last_name.find(".") + 1:]
                else:
                    last_name = name
                excludes.add(last_name)
                print_msg("   skip module due syntax error: {} ({}/{})"
                          .format(last_name, i + 1, max_atemps))
        return []

    @meta_profiler("extract_modules")
    def _extract_modules_provenance(self, metascript, python_modules):
        """Return a set of module dependencies in the form:
            (name, version, path, code_hash)
        Store module provenance in the content database
        """
        modules = metascript.modules_store
        dependencies = metascript.dependencies_store
        modules.id = Module.id_seq()
        for name, module in viewitems(python_modules):
            if name != "__main__":
                version = self._get_version(name)
                path = module.__file__
                if path is None:
                    code_hash = None
                else:
                    with open(path, "rb") as f:
                        code_hash = content.put(f.read())
                info = (name, version, path, code_hash)
                mid = Module.fast_load_module_id(*info) or modules.add(*info)
                dependencies.add(mid)

    def _get_version(self, module_name):
        """Get module version"""
        # Check built-in module
        if module_name in sys.builtin_module_names:
            return platform.python_version()

        # Check package declared module version
        try:
            # TODO: This is slow! Is there any alternative?
            return pkg_resources.get_distribution(module_name).version
        except:
            pass

        # Check explicitly declared module version
        try:
            module = importlib.import_module(module_name)
            for attr in ["__version__", "version", "__VERSION__", "VERSION"]:
                try:
                    version = getattr(module, attr)
                    if isinstance(version, string):
                        return default_string(version)
                    if isinstance(version, tuple):
                        return ".".join(map(str, version))

                except AttributeError:
                    pass
        except:
            pass

        # If no other option work, return None
        return None

    @meta_profiler("deployment")
    def collect_provenance(self, metascript):
        """Collect deployment provenance:
        - environment variables
        - modules dependencies

        metascript should have "trial_id" and "path"
        """
        print_msg("  registering environment attributes")
        self._collect_environment_provenance(metascript)

        if metascript.bypass_modules:
            print_msg("  using previously detected module dependencies "
                      "(--bypass-modules).")
        else:
            print_msg("  searching for module dependencies")
            self._collect_modules_provenance(metascript)
        self.store_provenance(metascript)

    def store_provenance(self, metascript):
        """Store deployment provenance"""
        tid = metascript.trial_id
        # Remove after save
        partial = True
        EnvironmentAttr.fast_store(tid, metascript.environment_attrs_store,
                                   partial)
        Module.fast_store(tid, metascript.modules_store, partial)
        Dependency.fast_store(tid, metascript.dependencies_store, partial)
