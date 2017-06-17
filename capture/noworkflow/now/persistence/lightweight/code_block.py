# Copyright (c) 2016 Universidade Federal Fluminense (UFF)
# Copyright (c) 2016 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""Lightweight Code Block"""
from __future__ import (absolute_import, print_function,
                        division, unicode_literals)

from ..models import CodeBlock
from .. import content

from .base import BaseLW, define_attrs


class CodeBlockLW(BaseLW):
    """Code Block lightweight object"""

    __slots__, attributes = define_attrs(
        ["trial_id", "id", "code_hash", "binary", "docstring"],
        ["code"],
    )
    nullable = set()
    model = CodeBlock

    def __init__(self, id_, trial_id, code, binary, docstring):
        # pylint: disable=too-many-arguments
        self.trial_id = trial_id
        self.id = id_  # pylint: disable=invalid-name
        self.code = code
        bin_code = code if binary else code.encode("utf-8")
        self.code_hash = content.put(bin_code)
        self.docstring = docstring or ""

    def is_complete(self):
        """The first CodeBlockLW cannot be removed from object store"""
        return self.id != 1

    def __repr__(self):
        return ("CodeBlockLW(id={0.id})").format(self)
