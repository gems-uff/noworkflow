# Copyright (c) 2014 Universidade Federal Fluminense (UFF), Polytechnic Institute of New York University.
# This file is part of noWorkflow. Please, consult the license terms in the LICENSE file.

from __future__ import absolute_import

import os
import sys
import traceback
import argparse

from .. import persistence
from .. import prov_definition
from .. import prov_deployment
from .. import prov_execution
from .. import utils
from .command import Command

def non_negative(string):
    value = int(string)
    if value < 0:
        raise argparse.ArgumentTypeError("%s is not a non-negative integer value" % string)
    return value

class Run(Command):

    def add_arguments(self):
        p = self.parser
        p.add_argument('-v', '--verbose', help='increase output verbosity', action='store_true')
        p.add_argument('-b', '--bypass-modules', help='bypass module dependencies analysis, assuming that no module changes occurred since last execution', action='store_true')
        p.add_argument('-c', '--depth-context', help='functions subject to depth computation when capturing activations (defaults to non-user)', choices=['non-user', 'all'], default='non-user')
        p.add_argument('-d', '--depth', type=non_negative, help='depth for capturing function activations (defaults to 1)', default=1)
        p.add_argument('-e', '--execution-provenance', help='execution provenance provider. (defaults to Profiler)', choices=['Profiler', 'InspectProfiler', 'Tracer'], default="Profiler")
        p.add_argument('--disasm', help='show script disassembly', action='store_true')
        p.add_argument('script', help = 'Python script to be executed', nargs=argparse.REMAINDER)

    def execute(self, args):
        utils.verbose = args.verbose

        utils.print_msg('removing noWorkflow boilerplate')
       
        args_script = args.script
        args.script = os.path.realpath(args.script[0])
        
        if not os.path.exists(args.script):  # TODO: check this using argparse
            utils.print_msg('the script does not exist', True)
            sys.exit(1)

        script_dir = os.path.dirname(args.script)
        sys.path[0] = script_dir # Replace now's dir with script's dir in front of module search path.

        # Clear argv
        sys.argv = args_script
        # Clear up the __main__ namespace
        import __main__
        __main__.__dict__.clear()
        __main__.__dict__.update({'__name__'    : '__main__',
                                  '__file__'    : args.script,
                                  '__builtins__': __builtins__,
                                 })

        with open(args.script) as f:
            metascript = {
                'code': f.read(),
                'path': args.script,
                'compiled': None,
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
                metascript['compiled'] = compile(
                    metascript['code'], metascript['path'], 'exec')
            exec(metascript['compiled'], __main__.__dict__)        
                
        except SystemExit as ex:
            prov_execution.disable()
            utils.print_msg('the execution exited via sys.exit(). Exit status: {}'.format(ex.code), ex.code > 0)
        except Exception as e:
            prov_execution.disable()
            print e
            utils.print_msg('the execution finished with an uncaught exception. {}'.format(traceback.format_exc()), True)
        else:
            prov_execution.disable()
            prov_execution.store()  # TODO: exceptions should be registered as return from the activation and stored in the database. We are currently ignoring all the activation tree when exceptions are raised.
            utils.print_msg('the execution of trial {} finished successfully'.format(persistence.trial_id))

        return prov_execution.provider
