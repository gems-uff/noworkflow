# Copyright (c) 2016 Universidade Federal Fluminense (UFF)
# Copyright (c) 2016 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""'(%)%now run' magics"""

from __future__ import absolute_import, division, print_function, unicode_literals

import argparse
import builtins
import os
import sys

from ...cmd.cmd_run import Run, run
from ...collection.metadata import LAST_TRIAL, Metascript
from ...persistence import content, persistence_config
from ...persistence.models import Trial
from .command import IpythonCommandMagic


class NowRun(IpythonCommandMagic, Run):
    """Run cells with noworkflow

    If it is in interactive mode (--interactive), it will use the context
    Otherwise, it will run in a subprocess, using the %%script magic.

    Please look at %%script? to understand --proc, --bg, --out and --err.

    The magic returns the trial of the run, read from the store of --dir
    (the current directory without it). The notebook stays connected to
    that store afterwards: Trial(), %now_sql and the other magics read it
    until the next %now_run connects to another.

    Examples
    --------
    ::
        In [1]: my_var = 2

        In [2]: %%now_run --name script1 $my_var 30
           ...: import sys
           ...: print(sys.argv[1])
           ...: print(sys.argv[2])
        2
        30
        Out[2]: <Trial 1>

    ::
        In [3]: %%now_run --name script2 -v
           ...: l = range(4)
           ...: c = sum(l)
           ...: print(c)
        [now] removing noWorkflow boilerplate
        [now] setting up local provenance store
        [now] collecting definition provenance
        [now]   registering user-defined functions
        [now] collecting deployment provenance
        [now]   registering environment attributes
        [now]   searching for module dependencies
        [now]   registering provenance from 0 modules
        [now] collection execution provenance
        [now]   executing the script
        6
        [now] the execution of trial 2 finished successfully
        Out[3]: <Trial 2>

        In [4]: trial = _

    ::
        In [5]: %now_run script1.py $my_var 30
        Out[5]: <Trial 1>

    ::
        In [6]: trial = %now_run --name script2 script2.py
        6

    """

    def add_arguments(self):
        super(NowRun, self).add_arguments()
        add_arg = self.add_argument
        add_arg(
            "--out",
            type=str,
            help="""The variable in which to store stdout from the script.
                If the script is backgrounded, this will be the stdout *pipe*,
                instead of the stdout text itself.
                """,
        )
        add_arg(
            "--err",
            type=str,
            help="""The variable in which to store stderr from the script.
                If the script is backgrounded, this will be the stderr *pipe*,
                instead of the stderr text itself.
                """,
        )
        add_arg(
            "--bg",
            action="store_true",
            help="""Whether to run the script in the background.
                If given, the only way to see the output of the command is
                with --out/err.
                """,
        )
        add_arg(
            "--proc",
            type=str,
            help="""The variable in which to store Popen instance.
                This is used only when --bg option is given.
                """,
        )
        add_arg(
            "--interactive",
            action="store_true",
            help="""Execute with the IPython context
                """,
        )
        add_arg(
            "params", nargs=argparse.REMAINDER, help="params to be passed to script"
        )

    def execute(self, func, line, cell, magic_cls):
        # Calculate noworkflow params and script params
        # pylint: disable=too-many-locals
        argv, args = self.arguments(func, line)
        params = args.params
        if params:
            argv = argv[: -len(params)]
        # The notebook stays connected to the store of this run, so that the
        # trial the magic returns, and every later query, read that store
        directory = args.dir or os.path.abspath(os.path.curdir)
        persistence_config.content_engine = args.content_engine
        persistence_config.connect(directory)

        if cell:
            filename = magic_cls.shell.mktempfile(data=cell, prefix="now_run_")
        else:
            filename = params[0]
            params = params[1:]

        metascript = Metascript().read_ipython_args(
            args,
            directory,
            filename,
            [filename] + params,
            not args.interactive,
            cmd=line,
        )

        if args.interactive:
            user_ns = magic_cls.shell.user_ns
            save__name__ = user_ns["__name__"]
            save__builtins__ = user_ns.get("__builtins__", builtins)
            save__main__ = sys.modules["__main__"]
            save__argv__ = sys.argv
            save__path__ = sys.path[0]

            metascript.namespace = user_ns

            metascript.clear_namespace(erase=False)
            metascript.clear_sys()
            sys.modules["__main__"] = magic_cls.shell.user_module
            run(metascript, args)

            user_ns["__name__"] = save__name__
            user_ns["__builtins__"] = save__builtins__
            sys.argv = save__argv__
            sys.path[0] = save__path__
            sys.modules["__main__"] = save__main__
            try:
                return Trial(metascript.trial_id)
            except Exception as exc:  # pylint: disable=broad-except
                print("Failed", exc)
                return None

        # Set execution line
        cmd = ("now run --create_last {directory} {args} {script} {params}").format(
            directory="" if args.dir else "--dir {}".format(directory),
            args=" ".join(argv),
            script=filename,
            params=" ".join(params),
        )
        script = magic_cls.shell.find_cell_magic("script").__self__
        script.shebang(cmd, "")

        trial_id = read_last_trial(os.path.join(directory, LAST_TRIAL))
        if trial_id is None:
            print("No trial was stored")
            return None
        try:
            return Trial(trial_id)
        except Exception as exc:  # pylint: disable=broad-except
            print("Failed", exc)
            return None


def read_last_trial(path):
    """The trial id that ``.last_trial`` at ``path`` names, or None"""
    try:
        with content.std_open(path, "r") as last:
            return last.read().strip() or None
    except FileNotFoundError:
        return None
