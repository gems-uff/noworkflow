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
from .persistence.data_objects import ObjectStore
from .persistence.data_objects import DefinitionLW, ObjectLW
from .persistence.data_objects import EnvironmentAttrLW, ModuleLW, DependencyLW
from .prov_definition.definition import Definition
from .models import Tag, Trial
from .utils import io


LAST_TRIAL = ".last_trial"
MAIN = 0
PACKAGE = 1
ALL = 2

CONTEXTS = {
    'main': MAIN,
    'package': PACKAGE,
    'all': ALL
}


class Metascript(object):

    def __init__(self):
        # Storage
        self.definitions_store = ObjectStore(DefinitionLW)
        self.objects_store = ObjectStore(ObjectLW)

        self.environment_attrs_store = ObjectStore(EnvironmentAttrLW)
        self.modules_store = ObjectStore(ModuleLW)
        self.dependencies_store = ObjectStore(DependencyLW)



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
        # Map of paths considered to their def : dict(str -> DefinitionLW)
        self.paths = {}
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

        # Passed arguments : str
        self.command = ""

    def __getitem__(self, item):
        return getattr(self, item)

    def __setitem__(self, key, value):
        return setattr(self, key, value)

    @property
    def path(self):
        """Return path"""
        return self._path

    @property
    def code_hash(self):
        return self.paths[self.path].code_hash

    @path.setter
    def path(self, path):
        """Set _path.
        Remove old path from paths list and add new one to it
        """

        if self._path:
            self.definitions_store.delete(self.paths[self._path])
            del self.paths[self._path]
        self._path = path
        if not path:
            return
        self.add_path(path, set_code=True)

    def add_path(self, path, set_code=False):
        """Add path to paths list"""
        with open(path, "rb") as script_file:
            code = script_file.read()
            if set_code:
                self.code = code
            self.paths[path] = self.definitions_store.dry_add(
                "", path, code, "FILE", None)


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

    def read_cmd_args(self, args, cmd=None):
        """ Read cmd line argument object """
        if not cmd:
            cmd = ' '.join(sys.argv[1:])
        self.command = cmd
        self.dir = args.dir or os.path.dirname(args.script)
        self.argv = args.argv
        self.should_create_last_file = args.create_last
        self.name = args.name or os.path.basename(args.argv[0])
        self._read_args(args)
        self.path = args.script
        return self

    def read_ipython_args(self, args, directory, filename, argv, create_last,
                          cmd=None):
        """ Read magic line argument object """
        if not cmd:
            cmd = 'run ' + ' '.join(argv)
        self.command = cmd
        self.dir = directory or os.path.dirname(filename)
        self.argv = argv
        self.should_create_last_file = create_last
        self.name = args.name or os.path.basename(filename)
        self._read_args(args)
        self.path = filename
        return self

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

        io.print_msg("setting up local provenance store")
        persistence.connect(self.dir)
        return self

    def read_restore_args(self, args):
        self.name = args.script
        self.bypass_modules = args.bypass_modules
        self.command = ' '.join(sys.argv[1:])

        self.local = args.local
        self.input = args.input
        self.dir = args.dir
        return self

    def create_last(self):
        """ Create file indicating last trial id """
        if self.should_create_last_file:
            lastname = os.path.join(os.path.dirname(self.path), LAST_TRIAL)
            with open(lastname, "w") as lastfile:
                lastfile.write(str(self.trial_id))

    def create_trial(self, args=None, run=True):
        """Create trial and assign a new id to it"""
        if args is None:
            args = " ".join(sys.argv[1:])
        now = datetime.now()
        try:
            self.trial_id = Trial.fast_store(
                now, self.name, self.code_hash, args,
                self.bypass_modules, self.command, run=run)
        except TypeError as e:
            if self.bypass_modules:
                io.print_msg("not able to bypass modules check because no "
                          "previous trial was found", True)
                io.print_msg("aborting execution", True)
            else:
                raise e

            sys.exit(1)
