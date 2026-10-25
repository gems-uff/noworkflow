# Copyright (c) 2016 Universidade Federal Fluminense (UFF)
# Copyright (c) 2016 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""'now run' command"""

from __future__ import absolute_import, division, print_function, unicode_literals

import argparse
import os
import sys

from ..collection.metadata import Metascript
from ..collection.prov_execution.external import EXECUTABLE_CAP
from ..persistence import content
from ..persistence.models import Argument, Tag, Trial
from ..utils import io, metaprofiler
from .command import Command


def non_negative(string):
    """Check if argument is >= 0"""
    value = int(string)
    if value < 0:
        raise argparse.ArgumentTypeError(
            "{} is not a non-negative integer value".format(string)
        )
    return value


SIZE_SUFFIXES = {"": 1, "K": 1024, "M": 1024**2, "G": 1024**3}


def size(string):
    """Check if argument is a size in bytes, with an optional K, M or G
    suffix (powers of 1024)"""
    text = string.strip().upper()
    suffix = text[-1:] if text[-1:] in SIZE_SUFFIXES else ""
    digits = text[: len(text) - len(suffix)]
    if not digits.isdigit():
        raise argparse.ArgumentTypeError(
            "{!r} is not a size in bytes (such as 1000, 512K, 64M or 1G)".format(string)
        )
    return int(digits) * SIZE_SUFFIXES[suffix]


class ScriptArgs(argparse.Action):  # pylint: disable=too-few-public-methods
    """Action to create script attribute"""

    def __call__(self, parser, namespace, values, option_string=None):
        if not values:
            raise argparse.ArgumentError(self, "can't be empty")

        script = os.path.realpath(values[0])

        if not os.path.exists(script):
            raise argparse.ArgumentError(
                self,
                "can't open file '{}': [Errno 2] No such file or directory".format(
                    values[0]
                ),
            )

        setattr(namespace, self.dest, script)
        setattr(namespace, "argv", values)


def run(metascript, args=None):
    """Execute noWokflow to capture provenance from script

    Returns the exit status of the script: the one it passed to
    ``sys.exit``, 1 after an uncaught exception, 0 otherwise. The trial is
    stored before, whichever way the script ended.
    """
    args = args or []
    try:
        metascript.trial_id = Trial.create(*metascript.create_trial_args())
        metascript.create_arguments(args)
        arguments = metascript.arguments_store
        Argument.store(arguments, True)

        io.print_msg("collecting deployment provenance")
        metascript.deployment.collect_provenance()

        io.print_msg("collection definition and execution provenance")
        metascript.execution.collect_provenance()
        metascript.deployment.store_provenance()
        metascript.definition.store_provenance()
        metascript.execution.store_provenance()

        Tag.create_automatic_tag(*metascript.create_automatic_tag_args())
        Trial.set_user_based_on_env(metascript.trial_id)
        metaprofiler.meta_profiler.save()
        content.commit_content(
            metascript.message or "Trial {}".format(metascript.trial_id)
        )
    finally:
        metascript.create_last()
    return metascript.execution.exit_code


class Run(Command):
    """Run a script collecting its provenance"""

    def __init__(self, *args, **kwargs):
        super(Run, self).__init__(*args, **kwargs)
        self.default_context = "main"
        self.default_serializer = "repr"
        self.default_collect_values = "all"
        self.default_call_storage_frequency = 10000
        self.default_save_frequency = 0
        self.add_help = False

    def add_arguments(self):
        add_arg = self.add_argument
        add_cmd = self.add_argument_cmd

        # It will create both script and argv var
        add_cmd(
            "script",
            nargs=argparse.REMAINDER,
            action=ScriptArgs,
            help="Python script to be executed",
        )

        # Deployment
        if not self.is_ipython:
            deployment = self.parser.add_argument_group("optional deployment arguments")
            add_arg = deployment.add_argument
        add_arg(
            "-b",
            "--bypass-modules",
            action="store_true",
            help="bypass module dependencies analysis, assuming that no "
            "module changes occurred since last execution",
        )
        add_arg(
            "--executable-cap",
            type=size,
            default=EXECUTABLE_CAP,
            metavar="SIZE",
            help="R|size above which the program a process runs is not\n"
            "stored, only its hash (default: 16M). SIZE is in bytes,\n"
            "with an optional K, M or G suffix; 0 stores no program",
        )

        # Execution
        if not self.is_ipython:
            execution = self.parser.add_argument_group("optional execution arguments")
            add_arg = execution.add_argument
        add_arg(
            "-d",
            "--depth",
            type=non_negative,
            default=sys.getrecursionlimit(),
            help="depth for capturing function activations (default: recursion limit)",
        )
        # ToDo: limit module depth
        add_arg(
            "-r",
            "--serializer",
            choices=["repr", "jsonpickle", "jsonpickle_content", "simple"],
            default=self.default_serializer,
            help="serialization method for evaluation values (default: repr)",
        )
        add_arg(
            "-e",
            "--collect-values",
            choices=["none", "relevant", "all"],
            default=self.default_collect_values,
            help="R|collect evaluation values (default: all).\n"
            "The 'relevant' option makes it collect only values of activations,\n"
            "arguments, and tagged evaluations.",
        )
        #   Use context option: main, package, all
        add_arg(
            "-c",
            "--context",
            choices=["main", "package", "all"],
            default=self.default_context,
            help="functions subject to depth computation when capturing "
            "activations (default: main)",
        )
        add_arg(
            "-s",
            "--save-frequency",
            type=non_negative,
            default=self.default_save_frequency,
            help="frequency (in ms) to save partial provenance",
        )
        add_arg(
            "-S",
            "--call-storage-frequency",
            type=non_negative,
            default=self.default_call_storage_frequency,
            help="frequency (in calls) to save partial provenance",
        )
        # ToDo: capture only activations
        add_arg(
            "-cg",
            "--coarse-granularity",
            action="store_true",
            help="capture only activation-level provenance "
            "(activations, arguments, returns and file accesses)",
        )
        add_arg(
            "--external-tracer",
            choices=["none", "argv", "strace"],
            default="argv",
            help="R|how the processes the script starts are recorded "
            "(default: argv).\n"
            "argv records the files their command lines name, with\n"
            "their content before and after, and the files they create\n"
            "in the project; none records nothing of them; strace\n"
            "(Linux, with strace) also records every file of the\n"
            "project they and their children open, and falls back to\n"
            "argv with a warning where strace cannot trace",
        )

        # Other
        if not self.is_ipython:
            other = self.parser.add_argument_group("other optional arguments")
            add_arg = other.add_argument
        add_arg("-h", "--help", action="help", help="show this help message and exit")
        add_arg(
            "--name",
            type=str,
            help="R|set script name.\n"
            "This options allows separating or grouping trials \n"
            "in disjoint branches in the history. It is specially\n"
            "useful from grouping Jupyter Cells",
        )
        add_arg(
            "--dir",
            type=str,
            help="set project path. The noworkflow database folder will "
            "be created in this path. Default to script directory",
        )
        add_arg(
            "-v", "--verbose", action="store_true", help="increase output verbosity"
        )
        add_arg(
            "--message",
            type=str,
            default=None,
            help="add a message to the commit of the trial",
        )
        add_arg("--content-engine", type=str, help="set the content database engine")

        # Internal
        add_cmd("--create_last", action="store_true", help=argparse.SUPPRESS)
        add_arg("--meta", action="store_true", help=argparse.SUPPRESS)

    def execute(self, args):
        if args.meta:
            metaprofiler.meta_profiler.active = False
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
        return run(metascript, args)
