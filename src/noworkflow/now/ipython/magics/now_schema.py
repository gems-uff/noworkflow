# Copyright (c) 2016 Universidade Federal Fluminense (UFF)
# Copyright (c) 2016 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""'%now_schema' magic"""
from __future__ import (absolute_import, print_function,
                        division, unicode_literals)

from sqlalchemy.schema import CreateTable

from ...cmd.cmd_schema import Schema

from ...utils.formatter import PrettyLines
from ...persistence.models import ORDER
from ...persistence import relational

from .command import IpythonCommandMagic


class NowSchema(IpythonCommandMagic, Schema):
    """Present Schema

    Examples
    --------
    ::
        In [1]: %now_schema sql -t
        Out[1]: CREATE TABLE trial (
                ...

        In [2]: %now_schema prolog --format png
        Out[2]: <png graph>
    """

    def __init__(self, *args, **kwargs):
        super(NowSchema, self).__init__(*args, **kwargs)
        self.format = "svg"

    def add_arguments(self):
        super(NowSchema, self).add_arguments()
        add_arg = self.add_argument
        add_arg("-f", "--format", type=str.lower, default="svg",
                choices=["svg", "png"],
                help="Graph format for diagram export (default: svg)")
        add_arg("-t", "--text", action="store_true",
                help="export textual schema")

    def post_process(self, result, args):
        """Transform result into image or PrettyLines"""                         # pylint: disable=no-self-use
        if args.diagram:
            result.format = self.format
            return result
        return PrettyLines(result)

    def execute(self, func, line, cell, magic_cls):
        _, args = self.arguments(func, line)
        args.diagram = not args.text
        self.format = args.format
        return self.process(args)
