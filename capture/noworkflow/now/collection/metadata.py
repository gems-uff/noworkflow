# Copyright (c) 2016 Universidade Federal Fluminense (UFF)
# Copyright (c) 2016 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
""" Define Metadata classes to be used as configuration """
from __future__ import (absolute_import, print_function,
                        division, unicode_literals)

import fnmatch
import os
import sys

from datetime import datetime

from pyposast import native_decode_source

from ..persistence import persistence_config, get_serializer
from ..persistence.lightweight import ObjectStore
from ..persistence.lightweight import DefinitionLW, ObjectLW
from ..persistence.lightweight import EnvironmentAttrLW
from ..persistence.lightweight import ModuleLW, DependencyLW
from ..persistence.lightweight import ActivationLW, ObjectValueLW
from ..persistence.lightweight import FileAccessLW, VariableLW
from ..persistence.lightweight import VariableUsageLW, VariableDependencyLW
from ..utils import io

from .prov_definition.definition import Definition
from .prov_execution.execution import Execution
from .prov_deployment.deployment import Deployment


LAST_TRIAL = ".last_trial"
MAIN = 0
PACKAGE = 1
ALL = 2

CONTEXTS = {
    "main": MAIN,
    "package": PACKAGE,
    "all": ALL
}


class Metascript(object):                                                        # pylint: disable=too-many-instance-attributes
    """Metascript object. Contain storages and arguments"""

    def __init__(self):
        # Storage
        self.definitions_store = ObjectStore(DefinitionLW)
        self.objects_store = ObjectStore(ObjectLW)

        self.environment_attrs_store = ObjectStore(EnvironmentAttrLW)
        self.modules_store = ObjectStore(ModuleLW)
        self.dependencies_store = ObjectStore(DependencyLW)

        self.activations_store = ObjectStore(ActivationLW)
        self.object_values_store = ObjectStore(ObjectValueLW)
        self.file_accesses_store = ObjectStore(FileAccessLW)

        self.variables_store = ObjectStore(VariableLW)
        self.variables_dependencies_store = ObjectStore(VariableDependencyLW)
        self.usages_store = ObjectStore(VariableUsageLW)

        # Definition object : Definition
        self.definition = Definition(self)
        self.execution = Execution(self)
        self.deployment = Deployment(self)

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
        # Script docstring
        self.docstring = ""

        # Verbose print
        self.verbose = False
        # Should it create a file with the last executed trial id : bool
        self.should_create_last_file = False
        # Profile noWorkflow itself
        self.meta = False

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
        # Script context : ["main", "package", "all"]
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
        """Return code_hash of trial script"""
        return self.paths[self.path].code_hash

    @path.setter
    def path(self, path):
        """Set _path.
        Remove old path from paths list and add new one to it
        """

        if self._path:
            self.definitions_store.remove(self.paths[self._path])
            del self.paths[self._path]
        self._path = path
        if not path:
            return
        self.add_path(path, set_code=True)

    def add_path(self, path, set_code=False):
        """Add path to paths list"""
        with open(path, "rb") as script_file:
            code = native_decode_source(script_file.read())
            if set_code:
                self.code = code
            self.paths[path] = self.definitions_store.dry_add(
                "", path, code, "FILE", None, 0, 0, "")

    def fake_path(self, path, code):
        """Fake configuration for tests"""
        self.name = path
        self._path = path
        self.code = native_decode_source(code)
        self.paths[path] = self.definitions_store.dry_add(
            "", path, self.code, "FILE", None, 0, 0, "")

    @property
    def context(self):
        """Return context"""
        return self._context

    @context.setter
    def context(self, context):
        """Set context
        Must be set AFTER self.non_user_depth
        """
        self._context = CONTEXTS[context]
        if self._context in (PACKAGE, ALL):
            dirname = os.path.dirname(self.path)
            for root, _, filenames in os.walk(dirname):
                for filename in fnmatch.filter(filenames, "*.py"):
                    self.add_path(os.path.join(root, filename))
        if context == ALL:
            self.non_user_depth = self.depth

    def clear_namespace(self, erase=True):
        """Clear namespace dict"""
        if erase:
            self.namespace.clear()
        self.namespace.update({
            "__name__": "__main__",
            "__file__": self.path,
            "__builtins__": __builtins__,
        })

    def clear_sys(self):
        """Clear sys variables"""
        # Replace now's dir with script's dir in front of module search path.
        sys.path[0] = self.dir
        # Clear argv
        sys.argv = self.argv

    def read_cmd_args(self, args, cmd=None):
        """Read cmd line argument object"""
        if not cmd:
            cmd = " ".join(sys.argv[1:])
        self.command = cmd
        self.dir = args.dir or os.path.dirname(args.script)
        self.argv = args.argv
        self.should_create_last_file = args.create_last
        self.name = args.name or os.path.basename(args.argv[0])
        self._read_args(args)
        self.path = args.script
        self.context = args.context
        return self

    def read_ipython_args(self, args, directory, filename, argv, create_last,   # pylint: disable=too-many-arguments
                          cmd=None):
        """Read magic line argument object"""
        if not cmd:
            cmd = "run " + " ".join(argv)
        self.command = cmd
        self.dir = directory or os.path.dirname(filename)
        self.argv = argv
        self.should_create_last_file = create_last
        self.name = args.name or os.path.basename(filename)
        self._read_args(args)
        self.path = filename
        self.context = args.context
        return self

    def _read_args(self, args):
        """Read cmd line argument object"""
        # ToDo #54: add serializer param
        self.serialize = get_serializer(args)
        self.verbose = args.verbose
        self.meta = args.meta

        self.disasm = args.disasm
        self.disasm0 = args.disasm0
        self.bypass_modules = args.bypass_modules

        self.depth = args.depth
        self.non_user_depth = args.non_user_depth
        self.execution_provenance = args.execution_provenance
        self.save_frequency = args.save_frequency
        self.call_storage_frequency = args.call_storage_frequency

        io.print_msg("setting up local provenance store")
        persistence_config.connect(self.dir)
        return self

    def read_restore_args(self, args):
        """Read cmd line argument object for 'now restore'"""
        self.bypass_modules = True
        self.command = " ".join(sys.argv[1:])

        self.dir = args.dir
        return self

    def create_last(self):
        """Create file indicating last trial id"""
        if self.should_create_last_file:
            lastname = os.path.join(os.path.dirname(self.path), LAST_TRIAL)
            with open(lastname, "w") as lastfile:
                lastfile.write(str(self.trial_id))

    def create_trial_args(self, args=None, run=True):
        """Return arguments for Trial.store"""
        if args is None:
            args = " ".join(sys.argv[1:])
        now = datetime.now()
        return (
            now, self.name, self.code_hash, args,
            self.bypass_modules, self.command, run,
            self.docstring
        )

    def create_automatic_tag_args(self):
        """Return arguments for Tag.create_automatic_tag"""
        return (self.trial_id, self.code_hash, self.command)
