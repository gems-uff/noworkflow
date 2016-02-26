# Copyright (c) 2016 Universidade Federal Fluminense (UFF)
# Copyright (c) 2016 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""'now run' command"""
from __future__ import (absolute_import, print_function,
                        division, unicode_literals)

import argparse
import os
import sys

from ..collection.metadata import Metascript
from ..persistence.models import Tag, Trial
from ..utils import io, metaprofiler

from .command import Command


def non_negative(string):
    """Check if argument is >= 0"""
    value = int(string)
    if value < 0:
        raise argparse.ArgumentTypeError(
            "{} is not a non-negative integer value".format(string))
    return value


class ScriptArgs(argparse.Action):                                               # pylint: disable=too-few-public-methods
    """Action to create script attribute"""
    def __call__(self, parser, namespace, values, option_string=None):
        if not values:
            raise argparse.ArgumentError(
                self, "can't be empty")

        script = os.path.realpath(values[0])

        if not os.path.exists(script):
            raise argparse.ArgumentError(
                self, "can't open file '{}': "
                "[Errno 2] No such file or directory".format(values[0]))

        setattr(namespace, self.dest, script)
        setattr(namespace, "argv", values)


def run(metascript):
    """Execute noWokflow to capture provenance from script"""
    try:
        metascript.trial_id = Trial.store(*metascript.create_trial_args())
        Tag.create_automatic_tag(*metascript.create_automatic_tag_args())

        io.print_msg("collecting definition provenance")
        metascript.definition.collect_provenance()
        metascript.definition.store_provenance()

        io.print_msg("collecting deployment provenance")
        metascript.deployment.collect_provenance()
        metascript.deployment.store_provenance()

        io.print_msg("collection execution provenance")
        metascript.execution.collect_provenance()
        metascript.execution.store_provenance()

        metaprofiler.meta_profiler.save()

    finally:
        metascript.create_last()


class Run(Command):
    """Run a script collecting its provenance"""

    def __init__(self, *args, **kwargs):
        super(Run, self).__init__(*args, **kwargs)
        self.default_context = "main"
        self.default_call_storage_frequency = 10000
        self.default_save_frequency = 0
        self.default_execution_provenance = "Profiler"

    def add_arguments(self):
        add_arg = self.add_argument
        add_cmd = self.add_argument_cmd
        add_arg("--name", type=str,
                help="set branch name used for tracking history")
        add_arg("--dir", type=str,
                help="set project path. The noworkflow database folder will "
                     "be created in this path. Default to script directory")
        # It will create both script and argv var
        add_cmd("script", nargs=argparse.REMAINDER, action=ScriptArgs,
                help="Python script to be executed")

        add_cmd("--create_last", action="store_true")
        add_arg("-v", "--verbose", action="store_true",
                help="increase output verbosity")
        add_arg("--meta", action="store_true",
                help="execute noWorkflow meta profiler")

        # Deployment
        add_arg("-b", "--bypass-modules", action="store_true",
                help="bypass module dependencies analysis, assuming that no "
                     "module changes occurred since last execution")

        # Definition
        add_arg("--disasm0", action="store_true",
                help="show script disassembly before noWorkflow change it")
        add_arg("--disasm", action="store_true",
                help="show script disassembly")

        # Execution
        add_arg("-d", "--depth", type=non_negative,
                default=sys.getrecursionlimit(),
                help="depth for capturing function activations (defaults to "
                     "recursion limit)")
        add_arg("-D", "--non-user-depth", type=non_negative, default=1,
                help="depth for capturing function activations outside the "
                     "selected context (defaults to 1)")
        add_arg("-e", "--execution-provenance",
                default=self.default_execution_provenance,
                choices=["Profiler", "Tracer", "Tracker"],
                help="execution provenance provider. (defaults to Profiler)")
        add_arg("-c", "--context", choices=["main", "package", "all"],
                default=self.default_context,
                help="functions subject to depth computation when capturing "
                     "activations (defaults to main)")
        add_arg("-s", "--save-frequency", type=non_negative,
                default=self.default_save_frequency,
                help="frequency (in ms) to save partial provenance")
        add_arg("-S", "--call-storage-frequency", type=non_negative,
                default=self.default_call_storage_frequency,
                help="frequency (in calls) to save partial provenance")

    def execute(self, args):
        if args.meta:
            metaprofiler.meta_profiler.active = True
            metaprofiler.meta_profiler.data["cmd"] = " ".join(sys.argv)

        io.verbose = args.verbose
        io.print_msg("removing noWorkflow boilerplate")

        # Create Metascript with params
        metascript = Metascript().read_cmd_args(args)

        # Set __main__ namespace
        import __main__
        metascript.namespace = __main__.__dict__

        # Clear boilerplate
        metascript.clear_sys()
        metascript.clear_namespace()

        # Run script
        run(metascript)
