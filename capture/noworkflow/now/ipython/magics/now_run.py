# Copyright (c) 2015 Universidade Federal Fluminense (UFF)
# Copyright (c) 2015 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.

from __future__ import (absolute_import, print_function,
                        division, unicode_literals)

import os
import sys
import argparse

from ...cmd import Run, LAST_TRIAL
from ...persistence import persistence
from ...models.trial import Trial


from .command import IpythonCommandMagic


class NowRun(IpythonCommandMagic, Run):
    """Run cells with noworkflow in a subprocess

    This uses the %%script magic.
    Please look at %%script? to understand --proc, --bg, --out and --err.

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
        argv, args = self.arguments(func, line)
        params = args.params
        if params:
            argv = argv[:-len(params)]
        # Create tmp file
        directory = args.dir or os.path.abspath(os.path.curdir)
        original_path = persistence.path
        try:
            persistence.connect(directory)
            filename = ''
            if cell:
                #cell = cell.encode('utf8', 'replace')
                filename = magic_cls.shell.mktempfile(data=cell, prefix='now_run_')

            # Set execution line
            cmd = "now run --create_last {directory} {args} {script} {params}".format(
                directory='' if args.dir else '--dir {0}'.format(directory),
                args=' '.join(argv),
                script=filename,
                params=' '.join(params)
            )
            script = magic_cls.shell.find_cell_magic('script').__self__
            result = script.shebang(cmd, "")
            tmp_dir = os.path.dirname(filename or params[0])

            try:
                with open(os.path.join(tmp_dir, LAST_TRIAL), 'r') as f:
                    return Trial(trial_id=int(f.read()))
            except e:
                print('Failed', e)
        finally:
            persistence.connect(original_path)
