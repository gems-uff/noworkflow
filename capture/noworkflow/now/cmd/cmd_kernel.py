# Copyright (c) 2016 Universidade Federal Fluminense (UFF)
# Copyright (c) 2016 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""'now vis' command"""
from __future__ import (absolute_import, print_function,
                        division, unicode_literals)

import errno
import os
import sys
import threading
import webbrowser

from ipykernel import kernelspec
from ..persistence import persistence_config
from .command import Command

KERNEL_NAME = 'noworkflow%i' % sys.version_info[0]
DISPLAY_NAME = 'noWorkflow %i' % sys.version_info[0]

kernelspec.make_ipkernel_cmd.__defaults__ = ('noworkflow.kernel', None, None)

class Kernel(Command):
    """ Install Jupyter Kernel """

    def add_arguments(self):
        add_arg = self.add_argument
        add_arg('--user', action='store_true',
                help="Install for the current user instead of system-wide")
        add_arg('--name', type=str, default=KERNEL_NAME,
                help="Specify a name for the kernelspec. This is needed"
                " to have multiple kernels at the same time.")
        add_arg('--display-name', type=str, default=DISPLAY_NAME,
                help="Specify the display name for the kernelspec."
                " This is helpful when you have multiple kernels.")
        add_arg('--profile', type=str,
                help="Specify an IPython profile to load. "
                "This can be used to create custom versions of the kernel.")
        add_arg('--prefix', type=str,
                help="Specify an install prefix for the kernelspec."
                " This is needed to install into a non-default location,"
                " such as a conda/virtual-env.")
        add_arg('--sys-prefix', action='store_const', const=sys.prefix, 
                dest='prefix',
                help="Install to Python's sys.prefix."
                " Shorthand for --prefix='%s'. For use in conda/virtual-envs." %
                sys.prefix)

    def execute(self, args):
        try:
            dest = kernelspec.install(
                user=args.user, kernel_name=args.name, profile=args.profile,
                prefix=args.prefix, display_name=args.display_name)
        except OSError as e:
            if e.errno == errno.EACCES:
                print(e, file=sys.stderr)
                if args.user:
                    print("Perhaps you want `sudo` or `--user`?",
                          file=sys.stderr)
                self.exit(1)
            raise
        print("Installed kernelspec %s in %s" % (args.name, dest))
