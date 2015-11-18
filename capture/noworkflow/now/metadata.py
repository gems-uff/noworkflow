# Copyright (c) 2015 Universidade Federal Fluminense (UFF)
# Copyright (c) 2015 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
""" Define Metadata classes to be used as configuration """
from __future__ import (absolute_import, print_function,
                        division, unicode_literals)

import fnmatch
import os
import sys

from datetime import datetime
from .persistence import persistence, get_serialize
from .prov_definition.definition import Definition
from .utils.io import print_msg


LAST_TRIAL = ".last_trial"
MAIN = 0
PACKAGE = 1
ALL = 2

CONTEXTS = {
    'main': MAIN,
    'package': PACKAGE,
    'all': ALL
}


class RunMetascript(object):

    def __init__(self):
        # Trial id read from Database : int
        self.trial_id = None
        # Trial name : str
        self.name = None
        # Source code of the main script : str
        self.code = None
        # Compiled code : types.CodeType
        self.compiled = None
        # Script dir : str
        self.dir = None
        # Main path : str
        self._path = None
        # List of paths considered : set(str)
        self.paths = set(str())
        # Main namespace : dict
        self.namespace = None
        # Argv
        self.argv = None
        # Object Serialize function
        self.serialize = None

        # Verbose print
        self.verbose = False
        # Should it create a file with the last executed trial id : bool
        self.should_create_last_file = False
        # Profile noWorkflow itself
        self.meta = False

        # Definition object : Definition
        self.definition = Definition()
        # Show script disassembly : bool
        self.disasm = False
        # Show script disassembly before changes : bool
        self.disasm0 = False

        # Bypass module check : bool
        self.bypass_modules = False

        # Depth for capturing function activations : int
        self.depth = sys.getrecursionlimit()
        # Depth for capturing function activations outside context : int
        self.non_user_depth = 1
        # Execution provenance provider : str
        self.execution_provenance = "Profiler"
        # Script context : ['main', 'package', 'all']
        self._context = MAIN
        # Save every X ms : int
        self.save_frequency = 1000
        # Save after closing X activations
        self.call_storage_frequency = 0

    def __getitem__(self, item):
        return getattr(self, item)

    def __setitem__(self, key, value):
        return setattr(self, key, value)

    @property
    def path(self):
        """ Return path """
        return self._path

    @path.setter
    def path(self, path):
        """ Set _path.
            Remove old path from paths list and add new one to it """
        if self._path:
            self.paths.remove(self._path)
        self._path = path
        if not path:
            return
        with open(path, "rb") as script_file:
            self.code = script_file.read()
        self.paths.add(path)
        self.dir = self.dir or os.path.dirname(path)

    def add_path(self, path):
        """ Add path to paths list """
        self.paths.add(path)

    @property
    def context(self):
        """ Return context """
        return self._context

    @context.setter
    def context(self, context):
        """ Set context
            Must be set AFTER self.non_user_depth """
        self._context = CONTEXTS[context]
        if self._context in (PACKAGE, ALL):
            dirname = os.path.dirname(self.path)
            for root, _, filenames in os.walk(dirname):
                for filename in fnmatch.filter(filenames, "*.py"):
                    self.add_path(os.path.join(root, filename))
        if context == ALL:
            self.non_user_depth = self.depth

    def clear_namespace(self, erase=True):
        """ Clear namespace dict """
        if erase:
            self.namespace.clear()
        self.namespace.update({"__name__"    : "__main__",
                               "__file__"    : self.path,
                               "__builtins__": __builtins__,
                              })

    def clear_sys(self):
        """ Clear sys variables """
        # Replace now's dir with script's dir in front of module search path.
        sys.path[0] = self.dir
        # Clear argv
        sys.argv = self.argv

    def read_cmd_args(self, args):
        """ Read cmd line argument object """
        self.dir = args.dir
        self.argv = args.argv
        self.path = args.script
        self.should_create_last_file = args.create_last
        self.name = args.name or os.path.basename(args.argv[0])
        return self._read_args(args)

    def read_ipython_args(self, args, directory, filename, argv, create_last):
        """ Read magic line argument object """
        self.dir = directory
        self.argv = argv
        self.path = filename
        self.should_create_last_file = create_last
        self.name = args.name or os.path.basename(filename)
        return self._read_args(args)

    def _read_args(self, args):
        """ Read cmd line argument object """
        self.serialize = get_serialize(args) # ToDo: add serializer param
        self.verbose = args.verbose
        self.meta = args.meta

        self.disasm = args.disasm
        self.disasm0 = args.disasm0
        self.bypass_modules = args.bypass_modules

        self.depth = args.depth
        self.non_user_depth = args.non_user_depth
        self.execution_provenance = args.execution_provenance
        self.context = args.context
        self.save_frequency = args.save_frequency
        self.call_storage_frequency = args.call_storage_frequency
        return self

    def create_last(self):
        """ Create file indicating last trial id """
        if self.should_create_last_file:
            lastname = os.path.join(os.path.dirname(self.path), LAST_TRIAL)
            with open(lastname, "w") as lastfile:
                lastfile.write(str(self.trial_id))

    def create_trial(self):
        """ Create trial and assign a new id to it """
        now = datetime.now()
        try:
            self.trial_id = persistence.store_trial(
                now, self.name, self.code, " ".join(sys.argv[1:]),
                self.bypass_modules)
        except TypeError as e:
            if self.bypass_modules:
                print_msg("not able to bypass modules check because no "
                          "previous trial was found", True)
                print_msg("aborting execution", True)
            else:
                raise e

            sys.exit(1)
