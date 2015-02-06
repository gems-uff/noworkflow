# Copyright (c) 2014 Universidade Federal Fluminense (UFF)
# Copyright (c) 2014 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.

from __future__ import (absolute_import, print_function,
                        division, unicode_literals)

import os
import sys
import traceback
import argparse

from .. import prov_definition
from .. import prov_deployment
from .. import prov_execution
from .. import utils
from ..persistence import persistence
from ..cross_version import cross_compile
from .command import Command

def non_negative(string):
    value = int(string)
    if value < 0:
        raise argparse.ArgumentTypeError(
            "%s is not a non-negative integer value" % string)
    return value

class Run(Command):

    def add_arguments(self):
        add_arg = self.parser.add_argument
        add_arg('-v', '--verbose', action='store_true',
                help='increase output verbosity')
        add_arg('-b', '--bypass-modules', action='store_true',
                help='bypass module dependencies analysis, assuming that no '
                     'module changes occurred since last execution')
        add_arg('-c', '--depth-context', choices=['non-user', 'all'],
                default='non-user',
                help='functions subject to depth computation when capturing '
                     'activations (defaults to non-user)')
        add_arg('-d', '--depth', type=non_negative, default=1,
                help='depth for capturing function activations (defaults to '
                     '1)')
        add_arg('-e', '--execution-provenance', default="Profiler",
                choices=['Profiler', 'InspectProfiler', 'Tracer'],
                help='execution provenance provider. (defaults to Profiler)')
        add_arg('--disasm', action='store_true',
                help='show script disassembly')
        add_arg('script', nargs=argparse.REMAINDER,
                help='Python script to be executed')

    def execute(self, args):
        utils.verbose = args.verbose

        utils.print_msg('removing noWorkflow boilerplate')

        args_script = args.script
        args.script = os.path.realpath(args.script[0])

        if not os.path.exists(args.script):  # TODO: check this using argparse
            utils.print_msg('the script does not exist', True)
            sys.exit(1)

        # Replace now's dir with script's dir in front of module search path.
        script_dir = os.path.dirname(args.script)
        sys.path[0] = script_dir

        # Clear argv
        sys.argv = args_script
        # Clear up the __main__ namespace
        import __main__
        __main__.__dict__.clear()
        __main__.__dict__.update({'__name__'    : '__main__',
                                  '__file__'    : args.script,
                                  '__builtins__': __builtins__,
                                 })

        with open(args.script, 'rb') as f:
            metascript = {
                'trial_id': None,
                'code': f.read(),
                'path': args.script,
                'compiled': None,
                'definition': None,
            }

        self.run(script_dir, args, metascript, __main__)

    def run(self, script_dir, args, metascript, __main__):

        utils.print_msg('setting up local provenance store')
        persistence.connect(script_dir)

        utils.print_msg('collecting definition provenance')
        prov_definition.collect_provenance(args, metascript)

        utils.print_msg('collecting deployment provenance')
        prov_deployment.collect_provenance(args, metascript)

        utils.print_msg('collection execution provenance')
        prov_execution.enable(args, metascript)

        utils.print_msg('  executing the script')
        try:
            if metascript['compiled'] is None:
                metascript['compiled'] = cross_compile(
                    metascript['code'], metascript['path'], 'exec')
            exec(metascript['compiled'], __main__.__dict__)

        except SystemExit as ex:
            prov_execution.disable()
            utils.print_msg(
                'the execution exited via sys.exit(). Exit status: {}'
                ''.format(ex.code), ex.code > 0)
        except Exception as e:
            prov_execution.disable()
            print(e)
            utils.print_msg(
                'the execution finished with an uncaught exception. {}'
                ''.format(traceback.format_exc()), True)
        else:
            # TODO: exceptions should be registered as return from the
            # activation and stored in the database. We are currently ignoring
            # all the activation tree when exceptions are raised.
            prov_execution.disable()
            prov_execution.store()
            utils.print_msg(
                'the execution of trial {} finished successfully'
                ''.format(metascript['trial_id']))

        return prov_execution.provider
