# Copyright (c) 2016 Universidade Federal Fluminense (UFF)
# Copyright (c) 2016 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""Lightweight Remote"""
from __future__ import (absolute_import, print_function,
                        division, unicode_literals)


from ..models import Remote                        
from .base import BaseLW, define_attrs

class RemoteLW(BaseLW):                                                      # pylint: disable=too-many-instance-attributes
    """Remote lightweight object"""

    __slots__, attributes = define_attrs(
        ["relatedExperiment","server_url","name", "id", "used", "hide"]
    )
    nullable = set()
    model = Remote

    def __init__(self, id, server_url, name, used, hide):

        self.server_url = server_url
        self.id = id
        self.name = name
        self.used = used
        self.hide = hide
    
    def __json__(self):
        return {

            'server_url': self.server_url,
            'name': self.name,
            'id': self.id,
            'used': self.used,
            'hide': self.hide
        }