# Copyright (c) 2013 Universidade Federal Fluminense (UFF), Polytechnic Institute of New York University.
# This file is part of noWorkflow. Please, consult the license terms in the LICENSE file.

'Supporting infrastructure to run scientific experiments without a scientific workflow management system.'

import argparse

import cmd_diff
import cmd_export
import cmd_list
import cmd_run
import cmd_show


def non_negative(string):
    value = int(string)
    if value < 0:
        raise argparse.ArgumentTypeError("%s is not a non-negative integer value" % string)
    return value


def main():
    parser = argparse.ArgumentParser(description = __doc__)
    subparsers = parser.add_subparsers()

    # run subcomand
    parser_run = subparsers.add_parser('run', help='runs a script collecting its provenance')
    parser_run.add_argument('-v', '--verbose', help='increase output verbosity', action='store_true')
    parser_run.add_argument('-b', '--bypass-modules', help='bypass module dependencies analysis, assuming that no module changes occurred since last execution', action='store_true')
    parser_run.add_argument('-c', '--depth-context', help='functions subject to depth computation when capturing activations (defaults to non-user)', choices=['non-user', 'all'], default='non-user')
    parser_run.add_argument('-d', '--depth', type=non_negative, help='depth for capturing function activations (defaults to 1)', default=1)
    parser_run.add_argument('-e', '--execution-provenance', help='execution provenance provider. (defaults to Profiler)', choices=['Profiler', 'InspectProfiler'], default="Profiler")
    
    parser_run.add_argument('script', help = 'Python script to be executed', nargs=argparse.REMAINDER)
    parser_run.set_defaults(func=cmd_run.execute)

    # list subcomand
    parser_list = subparsers.add_parser('list', help='lists all trials registered in the current directory')
    parser_list.set_defaults(func=cmd_list.execute)

    # show subcomand
    parser_show = subparsers.add_parser('show', help='shows the collected provenance of a trial')
    parser_show.add_argument('trial', type=int, nargs='?', help='trial id or none for last trial')
    parser_show.add_argument('-m', '--modules', help='shows module dependencies', action='store_true')
    parser_show.add_argument('-d', '--function-defs', help='shows the user-defined functions', action='store_true')
    parser_show.add_argument('-e', '--environment', help='shows the environment conditions', action='store_true')
    parser_show.add_argument('-a', '--function-activations', help='shows function activations', action='store_true')
    parser_show.add_argument('-f', '--file-accesses', help='shows read/write access to files', action='store_true')
    parser_show.set_defaults(func=cmd_show.execute)

    # diff subcomand
    parser_diff = subparsers.add_parser('diff', help='compares the collected provenance of two trials')
    parser_diff.add_argument('trial', type=int, nargs=2, help='trial id to be compared')
    parser_diff.add_argument('-m', '--modules', help='compare module dependencies', action='store_true')
    parser_diff.add_argument('-e', '--environment', help='compare environment conditions', action='store_true')
    parser_diff.set_defaults(func=cmd_diff.execute)

    # export subcomand
    parser_export = subparsers.add_parser('export', help='exports the collected provenance of a trial to Prolog')
    parser_export.add_argument('trial', type=int, nargs='?', help='trial id or none for last trial')
    parser_export.add_argument('-r', '--rules', help='also exports inference rules', action='store_true')
    parser_export.set_defaults(func=cmd_export.execute)

    args, _ = parser.parse_known_args()
    args.func(args)


if __name__ == '__main__':
    import now #@UnresolvedImport
    now.main()
