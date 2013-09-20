'Supporting infrastructure to run scientific experiments without a scientific workflow management system.'
import sys
import argparse
import os
import posixpath

def main():
    parser = argparse.ArgumentParser(description = __doc__)
    parser.add_argument('script', help = 'Python script to be executed.')
    args = parser.parse_args()
    
    script_path = posixpath.realpath(args.script)
    script_name = posixpath.basename(script_path)
    script_dir = posixpath.dirname(script_path)
    
    if not os.path.exists(script_path):
        print '[noWorkflow] Error:', script_path, 'does not exist'
        sys.exit(1)

    del sys.argv[0] # Hide "now" from argument list
    sys.path[0] = script_dir # Replace now's dir with script's dir in front of module search path.

    try:
        #pdb._runscript(mainpyfile)
        exec(open(script_path).read()) 
        print '[noWorkflow] The program {0} finished SUCCESSFULLY'.format(script_name)
    except SystemExit:
        print '[noWorkflow] The program {0} exited via sys.exit(). Exit status: '.format(script_name),
        print sys.exc_info()[1]
    except:
        #traceback.print_exc()
        print '[noWorkflow] The program {0} finished with an uncaught exception:'.format(script_name)
        raise sys.exc_info()[2]


    
    