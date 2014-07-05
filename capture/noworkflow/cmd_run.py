# Copyright (c) 2013 Universidade Federal Fluminense (UFF), Polytechnic Institute of New York University.
# This file is part of noWorkflow. Please, consult the license terms in the LICENSE file.
import os
import sys
import traceback

import persistence
import prov_definition
import prov_deployment
import prov_execution
import utils


def execute(args):
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

    utils.print_msg('setting up local provenance store')
    persistence.connect(script_dir)

    utils.print_msg('collecting definition provenance')
    prov_definition.collect_provenance(args)

    utils.print_msg('collecting deployment provenance')
    prov_deployment.collect_provenance(args)

    utils.print_msg('collection execution provenance')
    prov_execution.enable(args)

    utils.print_msg('  executing the script')
    try:
        execfile(args.script, __main__.__dict__)
    except SystemExit as ex:
        prov_execution.disable()
        utils.print_msg('the execution exited via sys.exit(). Exit status: {}'.format(ex.code), ex.code > 0)
    except:
        prov_execution.disable()
        utils.print_msg('the execution finished with an uncaught exception. {}'.format(traceback.format_exc()), True)
    else:
        prov_execution.disable()
        prov_execution.store()  # TODO: exceptions should be registered as return from the activation and stored in the database. We are currently ignoring all the activation tree when exceptions are raised.
        utils.print_msg('the execution of trial {} finished successfully'.format(persistence.trial_id))
