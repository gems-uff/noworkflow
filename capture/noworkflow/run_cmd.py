# Copyright (c) 2013 Universidade Federal Fluminense (UFF), Polytechnic Institute of New York University.
# This file is part of noWorkflow. Please, consult the license terms in the LICENSE file.
import os
import sys
import traceback

import persistence
import prospective
import retrospective
from utils import print_msg
import utils

def execute(args):
    utils.verbose = args.verbose
    
    print_msg('removing noWorkflow boilerplate')
    while (sys.argv[0] != args.script):
        del sys.argv[0] # Hide now command and arguments from argument list
    args.script = os.path.realpath(args.script)
    if not os.path.exists(args.script):  # TODO: check this using argparse
        print_msg('the script does not exist', True)
        sys.exit(1)

    script_dir = os.path.dirname(args.script)
    sys.path[0] = script_dir # Replace now's dir with script's dir in front of module search path.
    
    # Clear up the __main__ namespace
    import __main__
    __main__.__dict__.clear()
    __main__.__dict__.update({'__name__'    : '__main__',
                              '__file__'    : args.script,
                              '__builtins__': __builtins__,
                             })

    print_msg('setting up local provenance store')
    persistence.connect(script_dir)

    print_msg('collecting prospective provenance')  # TODO: remove environment from prospective
    prospective.collect_provenance(args)

    print_msg('enabling collection of retrospective provenance')
    retrospective.enable(args)

    print_msg('executing the script')
    try:
        execfile(args.script, __main__.__dict__)
        retrospective.disable()
        print_msg('the execution of trial {} finished successfully'.format(persistence.trial_id))
    except SystemExit as ex:
        retrospective.disable()
        print_msg('the execution exited via sys.exit(). Exit status: {}'.format(ex.code), ex.code > 0)
    except:
        retrospective.disable()
        print_msg('the execution finished with an uncaught exception. {}'.format(traceback.format_exc()), True)
