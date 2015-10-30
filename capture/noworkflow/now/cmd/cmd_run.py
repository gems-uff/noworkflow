# Copyright (c) 2015 Universidade Federal Fluminense (UFF)
# Copyright (c) 2015 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
""" 'now run' command """
from __future__ import (absolute_import, print_function,
                        division, unicode_literals)

import argparse
import fnmatch
import os
import sys

from .command import Command
from .. import prov_definition
from .. import prov_deployment
from .. import prov_execution
from ..utils import io, metaprofiler
from ..persistence import persistence


LAST_TRIAL = '.last_trial'


def non_negative(string):
    """ Check if argument is >= 0 """
    value = int(string)
    if value < 0:
        raise argparse.ArgumentTypeError(
            "%s is not a non-negative integer value" % string)
    return value


def run(script_dir, args, metascript, namespace):
    """ Execute noWokflow to capture provenance from script """

    io.print_msg('setting up local provenance store')
    persistence.connect(script_dir)

    io.print_msg('collecting definition provenance')
    prov_definition.collect_provenance(args, metascript)

    io.print_msg('collecting deployment provenance')
    prov_deployment.collect_provenance(args, metascript)

    io.print_msg('collection execution provenance')
    prov_execution.collect_provenance(args, metascript, namespace)

    metaprofiler.meta_profiler.save()

    return prov_execution.provider


class Run(Command):
    """ Run a script collecting its provenance """

    def add_arguments(self):
        add_arg = self.add_argument
        add_cmd = self.add_argument_cmd
        add_arg('-v', '--verbose', action='store_true',
                help='increase output verbosity')
        add_arg('-b', '--bypass-modules', action='store_true',
                help='bypass module dependencies analysis, assuming that no '
                     'module changes occurred since last execution')
        add_arg('-c', '--context', choices=['main', 'package', 'all'],
                default='main',
                help='functions subject to depth computation when capturing '
                     'activations (defaults to main)')
        add_arg('-d', '--depth', type=non_negative,
                default=sys.getrecursionlimit(),
                help='depth for capturing function activations (defaults to '
                     'recursion limit)')
        add_arg('-D', '--non-user-depth', type=non_negative, default=1,
                help='depth for capturing function activations outside the '
                     'selected context (defaults to 1)')
        add_arg('-e', '--execution-provenance', default="Profiler",
                choices=['Profiler', 'InspectProfiler', 'Tracer'],
                help='execution provenance provider. (defaults to Profiler)')
        add_arg('--disasm', action='store_true',
                help='show script disassembly')
        add_arg('--meta', action='store_true',
                help='exeute noWorkflow meta profiler')
        add_arg('--name', type=str,
                help="set branch name used for tracking history")
        add_arg('--dir', type=str,
                help='set project path. The noworkflow database folder will '
                     'be created in this path. Default to script directory')
        add_cmd('--create_last', action='store_true')
        add_cmd('script', nargs=argparse.REMAINDER,
                help='Python script to be executed')

    def execute(self, args):

        if args.meta:
            metaprofiler.meta_profiler.active = True
            metaprofiler.meta_profiler.data['cmd'] = ' '.join(sys.argv)

        io.verbose = args.verbose
        io.print_msg('removing noWorkflow boilerplate')

        args_script = args.script
        args.script = os.path.realpath(args.script[0])

        if not os.path.exists(args.script):
            # TODO: check this using argparse
            io.print_msg('the script does not exist', True)
            sys.exit(1)

        script_dir = args.dir or os.path.dirname(args.script)

        # Replace now's dir with script's dir in front of module search path.
        sys.path[0] = os.path.dirname(args.script)

        # Clear argv
        sys.argv = args_script
        # Clear up the __main__ namespace
        import __main__
        __main__.__dict__.clear()
        __main__.__dict__.update({'__name__'    : '__main__',
                                  '__file__'    : args.script,
                                  '__builtins__': __builtins__,
                                 })

        with open(args.script, 'rb') as script_file:
            metascript = {
                'trial_id': None,
                'code': script_file.read(),
                'path': args.script,
                'paths': {args.script},
                'compiled': None,
                'definition': None,
                'name': args.name or os.path.basename(sys.argv[0])
            }
            if args.context in ('package', 'all'):
                path = os.path.dirname(args.script)
                for root, _, filenames in os.walk(path):
                    for filename in fnmatch.filter(filenames, '*.py'):
                        metascript['paths'].add(os.path.join(root, filename))
            if args.context == 'all':
                args.non_user_depth = args.depth
        try:
            run(script_dir, args, metascript, __main__.__dict__)
        finally:
            if args.create_last:
                tmp = os.path.join(os.path.dirname(args.script), LAST_TRIAL)
                with open(tmp, 'w') as last:
                    last.write(str(metascript['trial_id']))
