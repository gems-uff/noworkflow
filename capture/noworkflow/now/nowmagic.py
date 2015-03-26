# Copyright (c) 2014 Universidade Federal Fluminense (UFF)
# Copyright (c) 2014 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.

import os
import sys
import argparse

from IPython.core import magic_arguments
from IPython.core.magic import  (
    Magics, magics_class, line_magic, cell_magic, line_cell_magic
)
from IPython.utils.process import arg_split

from . import utils
from .cmd import Command, Run, LAST_TRIAL
from .persistence import persistence
from .models.trial import Trial

MAGIC_TYPES = {
    'cell': cell_magic,
    'line': line_magic,
    'line_cell': line_cell_magic
}


class IpythonCommandMagic(Command):

    def __init__(self, magic, docstring, magic_type='cell'):
        super(IpythonCommandMagic, self).__init__(docstring)
        self.magic = magic
        self.docstring = docstring
        self.magic_type = magic_type
        self.args = []

    def add_argument_cmd(self, *args, **kwargs):
        pass

    def add_argument(self, *args, **kwargs):
        self.args.append(
            magic_arguments.argument(*args, **kwargs)
        )

    def create_magic(self, f):
        f.__name__ = self.magic
        f.__doc__ = self.docstring
        f = MAGIC_TYPES[self.magic_type](self.magic)(f)
        for arg in self.args:
            f = arg(f)
        f = magic_arguments.magic_arguments()(f)
        return f

    def execute(self, args, shell):
        super(Command, self).execute(args)


class IpythonExternalRun(IpythonCommandMagic, Run):
    """Run cells with noworkflow in a subprocess

    This uses the %%script magic.
    Please look at %%script? to understand --proc, --bg, --out and --err.

    Examples
    --------
    ::
        In [1]: my_var = 2

        In [2]: %%now --name script1 $my_var 30
           ...: import sys
           ...: print(sys.argv[1])
           ...: print(sys.argv[2])
        2
        30

    ::
        In [3]: %%now --name script2 -v
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

    """

    def add_arguments(self):
        super(IpythonExternalRun, self).add_arguments()
        add_arg = self.add_argument
        add_arg('--out', type=str,
                help="""The variable in which to store stdout from the script.
                If the script is backgrounded, this will be the stdout *pipe*,
                instead of the stdout text itself.
                """)
        add_arg('--err', type=str,
                help="""The variable in which to store stderr from the script.
                If the script is backgrounded, this will be the stderr *pipe*,
                instead of the stderr text itself.
                """)
        add_arg('--bg', action="store_true",
                help="""Whether to run the script in the background.
                If given, the only way to see the output of the command is
                with --out/err.
                """)
        add_arg('--proc', type=str,
                help="""The variable in which to store Popen instance.
                This is used only when --bg option is given.
                """)
        add_arg('params', nargs=argparse.REMAINDER,
                help='params to be passed to script')

    def execute(self, func, line, cell, magic_cls):
        # Calculate noworkflow params and script params
        argv = arg_split(line, posix = not sys.platform.startswith('win'))
        args = magic_arguments.parse_argstring(func, line)
        params = args.params
        if params:
            argv = argv[:-len(params)]
        # Create tmp file
        directory = os.path.abspath(os.path.curdir)
        persistence.connect(directory)
        cell = cell.encode('utf8', 'replace')
        filename = magic_cls.shell.mktempfile(data=cell, prefix='now_run_')

        # Set execution line
        cmd = "now run --create_last --dir {directory} {args} {script} {params}".format(
            directory=directory,
            args=' '.join(argv),
            script=filename,
            params=' '.join(params)
        )
        script = magic_cls.shell.find_cell_magic('script').__self__
        result = script.shebang(cmd, "")
        tmp_dir = os.path.dirname(filename)

        try:
            with open(os.path.join(tmp_dir, LAST_TRIAL), 'r') as f:
                return Trial(trial_id=int(f.read()))
        except:
            pass


@magics_class
class NoworkflowMagics(Magics):

    def __init__(self, shell):
        super(NoworkflowMagics, self).__init__(shell=shell)
        self.commands = [
            IpythonExternalRun('now', IpythonExternalRun.__doc__)
        ]
        self._generate_magics()

    def __del__(self):
        self.kill_bg_processes()

    def _generate_magics(self):
        for command in self.commands:
            command.add_arguments()
            def func(line, cell):
                return command.execute(func, line, cell, self)

            func = command.create_magic(func)
            self.magics[command.magic_type][command.magic] = func
