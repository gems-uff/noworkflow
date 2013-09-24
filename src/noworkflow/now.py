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
from utils import write

def main():
    parser = argparse.ArgumentParser(description = __doc__)
    parser.add_argument("-v", "--verbose", help="increase output verbosity", action="store_true")
    parser.add_argument("-m", "--modules", help="list the module dependencies", action="store_true")
    parser.add_argument('script', help = 'Python script to be executed')
    args = parser.parse_args()
    
    script_path = os.path.realpath(args.script)
    script_dir = os.path.dirname(script_path)
    utils.verbose = args.verbose
    
    if not os.path.exists(script_path):
        write('the script does not exist', True)
        sys.exit(1)

    del sys.argv[0] # Hide "now" from argument list
    sys.path[0] = script_dir # Replace now's dir with script's dir in front of module search path.
    
    # Clear up the __main__ namespace
    import __main__
    __main__.__dict__.clear()
    __main__.__dict__.update({"__name__"    : "__main__",
                              "__file__"    : script_path,
                              "__builtins__": __builtins__,
                             })

    write('setting up local provenance store')
    persistence.connect(script_dir)

    write('collecting prospective provenance')
    prospective.collect_provenance(script_path, args.modules)

    write('enabling collection of retrospective provenance')
    # TODO: Register to listen trace calls
    # sys.settrace(???) 
    # sys.setprofile(???) <-- this seems more appropriate

    write('executing the script')
    try:
        execfile(script_path, __main__.__dict__) 
        write('the execution finished successfully')
    except SystemExit as ex:
        write('the execution exited via sys.exit(). Exit status: {}'.format(ex.code), ex.code > 0)
    except:
        write('the execution finished with an uncaught exception. {}'.format(traceback.format_exc()), True)
    finally:
        # TODO: Remove one of these
        sys.settrace(None)
        sys.setprofile(None)