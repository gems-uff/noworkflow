# Copyright (c) 2013 Universidade Federal Fluminense (UFF), Polytechnic Institute of New York University.
# This file is part of noWorkflow. Please, consult the license terms in the LICENSE file.

'Supporting infrastructure to run scientific experiments without a scientific workflow management system.'

import sys
import argparse
import os.path
import traceback
import persistence
import utils
import prospective
from utils import print_msg

def main():
    parser = argparse.ArgumentParser(description = __doc__)
    parser.add_argument("-v", "--verbose", help="increase output verbosity", action="store_true")
    parser.add_argument("-e", "--list-environment", help="list the environment conditions", action="store_true")
    parser.add_argument("-m", "--list-modules", help="list the module dependencies", action="store_true")
    parser.add_argument("-b", "--bypass-modules", help="bypass module dependencies analysis, assuming that no module changes occurred since last execution", action="store_true")
    parser.add_argument("-f", "--list-functions", help="list the user-defined functions", action="store_true")
    parser.add_argument('script', help = 'Python script to be executed')
    args = parser.parse_args()
    
    args.script = os.path.realpath(args.script)
    script_dir = os.path.dirname(args.script)
    utils.verbose = args.verbose
    
    if not os.path.exists(args.script):
        print_msg('the script does not exist', True)
        sys.exit(1)

    del sys.argv[0] # Hide "now" from argument list
    sys.path[0] = script_dir # Replace now's dir with script's dir in front of module search path.
    
    # Clear up the __main__ namespace
    import __main__
    __main__.__dict__.clear()
    __main__.__dict__.update({"__name__"    : "__main__",
                              "__file__"    : args.script,
                              "__builtins__": __builtins__,
                             })

    print_msg('setting up local provenance store')
    persistence.connect(script_dir)

    print_msg('collecting prospective provenance')
    prospective.collect_provenance(args)

    print_msg('enabling collection of retrospective provenance')
    # TODO: Register to listen trace calls
    # sys.settrace(???) 
    # sys.setprofile(???) <-- this seems more appropriate

    print_msg('executing the script')
    try:
        execfile(args.script, __main__.__dict__) 
        print_msg('the execution finished successfully')
    except SystemExit as ex:
        print_msg('the execution exited via sys.exit(). Exit status: {}'.format(ex.code), ex.code > 0)
    except:
        print_msg('the execution finished with an uncaught exception. {}'.format(traceback.format_exc()), True)
    finally:
        # TODO: Remove one of these
        sys.settrace(None)
        sys.setprofile(None)

if __name__ == '__main__':
    import now #@UnresolvedImport
    now.main()