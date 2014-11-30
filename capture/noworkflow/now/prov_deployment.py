# Copyright (c) 2014 Universidade Federal Fluminense (UFF)
# Copyright (c) 2014 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.

from __future__ import (absolute_import, print_function,
                        division, unicode_literals)

import importlib
import modulefinder
import os
import platform
import socket
import sys
import pkg_resources

from .persistence import persistence
from .utils import print_msg


def collect_environment_provenance():
    environment = {}
    e = environment

    environment['OS_NAME'] = platform.system()
    # Unix environment
    try:
        for name in os.sysconf_names:
            try:
                environment[name] = os.sysconf(name)
            except:
                pass
        for name in os.confstr_names:
            environment[name] = os.confstr(name)
        environment['USER'] = os.getlogin()
        e['OS_NAME'], _, e['OS_RELEASE'], e['OS_VERSION'], _ = os.uname()
    except:
        pass
    # Windows environment
    if environment['OS_NAME'] == 'Windows':
        e['OS_RELEASE'], e['OS_VERSION'], _, _ = platform.win32_ver()

    # Both Unix and Windows
    environment.update(os.environ)
    environment['PWD'] = os.getcwd()
    environment['PID'] = os.getpid()
    environment['HOSTNAME'] = socket.gethostname()
    environment['ARCH'] = platform.architecture()[0]
    environment['PROCESSOR'] = platform.processor()
    environment['PYTHON_IMPLEMENTATION'] = platform.python_implementation()
    environment['PYTHON_VERSION'] = platform.python_version()
    return environment


def collect_modules_provenance(modules):
    '''returns a set of module dependencies in the form:
        (name, version, path, code_hash)'''
    dependencies = []
    for name, module in modules.items():
        if name != '__main__':
            version = get_version(name)
            path = module.__file__
            if path == None:
                code_hash = None
            else:
                with open(path, 'rb') as f:
                    code_hash = persistence.put(f.read())
            dependencies.append((name, version, path, code_hash))
    return sorted(dependencies)


def get_version(module_name):
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
        for attr in ['__version__', 'version', '__VERSION__', 'VERSION']:
            try:
                version = getattr(module, attr)
                if isinstance(version, basestring):
                    return version
            except:
                pass
    except:
        pass

    # If no other option work, return None
    return None


def collect_provenance(args, metascript):
    print_msg('  registering environment attributes')
    environment = collect_environment_provenance()
    persistence.store_environment(metascript['trial_id'], environment)

    if args.bypass_modules:
        print_msg('  using previously detected module dependencies '
                  '(--bypass-modules).')
    else:
        print_msg('  searching for module dependencies')
        finder = modulefinder.ModuleFinder()
        finder.run_script(metascript['path'])

        print_msg('  registering provenance from {} modules'.format(
            len(finder.modules) - 1))
        modules = collect_modules_provenance(finder.modules)
        persistence.store_dependencies(metascript['trial_id'], modules)
