# Copyright (c) 2016 Universidade Federal Fluminense (UFF)
# Copyright (c) 2016 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
""" Define Metadata classes to be used as configuration """
from __future__ import (absolute_import, print_function,
                        division, unicode_literals)

import os
import sys

from argparse import Namespace
from datetime import datetime

from future.utils import viewitems

from ..persistence import persistence_config, get_serializer, content
from ..persistence.lightweight import ObjectStore, SharedObjectStore
from ..persistence.lightweight import ModuleLW
from ..persistence.lightweight import EnvironmentAttrLW, ArgumentLW
from ..persistence.lightweight import CodeComponentLW, CodeBlockLW
from ..persistence.lightweight import CompositionLW
from ..persistence.lightweight import EvaluationLW, ActivationLW, DependencyLW
from ..persistence.lightweight import ValueLW, CompartmentLW, FileAccessLW
from ..persistence.lightweight import ExceptionLW
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

    def __init__(self, **kwargs):
        # Storage
        self.arguments_store = ObjectStore(ArgumentLW)
        self.environment_attrs_store = ObjectStore(EnvironmentAttrLW)
        self.modules_store = ObjectStore(ModuleLW)

        self.code_components_store = ObjectStore(CodeComponentLW)
        self.code_blocks_store = SharedObjectStore(CodeBlockLW)
        self.compositions_store = ObjectStore(CompositionLW)

        self.evaluations_store = ObjectStore(EvaluationLW)
        self.activations_store = SharedObjectStore(ActivationLW)
        self.dependencies_store = ObjectStore(DependencyLW)
        self.values_store = ObjectStore(ValueLW)
        self.compartments_store = ObjectStore(CompartmentLW)
        self.file_accesses_store = ObjectStore(FileAccessLW)

        self.exceptions_store = ObjectStore(ExceptionLW)
        # Trial id read from Database : int
        self.trial_id = -1
        # Trial name : str
        self.name = ""
        # Compiled code : types.CodeType
        self.compiled = None
        # Script dir : str
        self.dir = ""
        # Main namespace : dict
        self.namespace = {}
        # Main path : str
        self.path = ""
        # Argv : list(str)
        self.argv = []
        # Object Serialize function : callable
        self.serialize = repr
        # Trial command : str
        self.command = ""
        # Main id : int
        self.main_id = 1
        # Code override. Just use it if you want to ignore path : str
        self.code = None

        # Verbose print : bool
        self.verbose = False
        # Should it create a file with the last executed trial id : bool
        self.should_create_last_file = False
        # Profile noWorkflow itself : bool
        self.meta = False

        # Bypass module check : bool
        self.bypass_modules = True

        # Capture func component : bool
        self.capture_func_component = False

        # Depth for capturing function activations : int
        self.depth = sys.getrecursionlimit()
        # Script context : ["main", "package", "all"]
        self._context = MAIN

        # Save every X ms : int
        self.save_frequency = None
        # Save after closing X activations : int
        self.call_storage_frequency = 0

        # Used by jupyter to indicate that it should not transform cell : bool
        self.jupyter_original = False


        # Definition object : Definition
        self.definition = Definition(self)
        self.execution = Execution(self)
        self.deployment = Deployment(self)

        for key, value in viewitems(kwargs):
            setattr(self, key, value)


    @property
    def context(self):
        """Return context"""
        return self._context

    @context.setter
    def context(self, context):
        """Set context"""
        self._context = CONTEXTS[context]

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

    def read_jupyter_args(self):
        """Read jupyter args"""
        self.command = " ".join(sys.argv)
        self.dir = os.getcwd()
        self.argv = sys.argv
        self.should_create_last_file = False
        self.name = "Jupyter Kernel"
        args = Namespace(
            verbose=False,
            meta=False,
            bypass_modules=False,
            depth=sys.getrecursionlimit(),
            save_frequency=0,
            call_storage_frequency=10000,
            context="main"
        )
        self._read_args(args)
        self.path = os.getcwd()
        self.context = args.context
        return self

    def _read_args(self, args):
        """Read cmd line argument object"""
        # ToDo #54: add serializer param
        self.serialize = get_serializer(args)
        self.verbose = args.verbose
        self.meta = args.meta

        self.bypass_modules = args.bypass_modules

        self.depth = args.depth
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

    def create_arguments(self, args):
        """Create arguments"""
        for arg in vars(args):
            value = getattr(args, arg)
            if arg not in ("func", ):
                self.arguments_store.add(self.trial_id, arg, repr(value))

    def create_last(self):
        """Create file indicating last trial id"""
        if self.should_create_last_file:
            lastname = os.path.join(self.dir, LAST_TRIAL)
            with content.std_open(lastname, "w") as lastfile:
                lastfile.write(str(self.trial_id))

    def create_automatic_tag_args(self):
        """Return arguments for Tag.create_automatic_tag"""
        return (
            self.trial_id,
            self.code_blocks_store[1].code_hash,
            self.command
        )

    def create_trial_args(self):
        """Return arguments for Trial.create"""
        return (
            self.name, datetime.now(), self.command,
            os.path.dirname(self.path),
            self.bypass_modules
        )
