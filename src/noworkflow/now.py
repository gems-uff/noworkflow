# Copyright (c) 2013 Universidade Federal Fluminense (UFF), Polytechnic Institute of New York University.
# This file is part of noWorkflow. Please, consult the license terms in the LICENSE file.

'Supporting infrastructure to run scientific experiments without a scientific workflow management system.'

import argparse
import run_cmd
import list_cmd
import show_cmd
import export_cmd

def main():
    parser = argparse.ArgumentParser(description = __doc__)
    subparsers = parser.add_subparsers()
    
    # run subcomand
    parser_run = subparsers.add_parser('run', help='runs a script collecting its provenance')
    parser_run.add_argument('-v', '--verbose', help='increase output verbosity', action='store_true')
    parser_run.add_argument('-b', '--bypass-modules', help='bypass module dependencies analysis, assuming that no module changes occurred since last execution', action='store_true')
    parser_run.add_argument('script', help = 'Python script to be executed')
    parser_run.set_defaults(func=run_cmd.execute)

    # list subcomand
    parser_list = subparsers.add_parser('list', help='lists all trials registered in the current directory')
    parser_list.set_defaults(func=list_cmd.execute)

    # show subcomand
    parser_show = subparsers.add_parser('show', help='shows the collected provenance of a trial')
    parser_show.add_argument('trial', type=int, nargs='?', help='trial id or none for last trial')
    parser_show.add_argument('-m', '--modules', help='shows module dependencies', action='store_true')
    parser_show.add_argument('-d', '--function-defs', help='shows the user-defined functions', action='store_true')
    parser_show.add_argument('-e', '--environment', help='shows the environment conditions', action='store_true')
    parser_show.add_argument('-c', '--function-calls', help='shows function calls', action='store_true')
    parser_show.add_argument('-a', '--file-accesses', help='shows read/write access to files', action='store_true')
    parser_show.set_defaults(func=show_cmd.execute)

    # export subcomand
    parser_export = subparsers.add_parser('export', help='exports the collected provenance of a trial')
    parser_export.add_argument('trial', type=int, help='trial id or none for last trial')
    parser_export.add_argument('-p', '--prolog', help='exports to prolog', action='store_true')
    parser_export.add_argument('-j', '--json', help='exports to json', action='store_true')
    parser_export.set_defaults(func=export_cmd.execute)
    
    args = parser.parse_args()
    args.func(args)


if __name__ == '__main__':
    import now #@UnresolvedImport
    now.main()