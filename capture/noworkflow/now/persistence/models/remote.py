# Copyright (c) 2016 Universidade Federal Fluminense (UFF)
# Copyright (c) 2016 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""Remote Model"""
from __future__ import (absolute_import, print_function,
                        division, unicode_literals)

from future.utils import lmap
from future.builtins import map as cvmap
from sqlalchemy import Column, String, Integer, ForeignKeyConstraint

from ...utils.prolog import PrologDescription, PrologTrial
from ...utils.prolog import PrologRepr, PrologTimestamp

from .. import relational

from .base import AlchemyProxy, proxy_class

@proxy_class
class Remote(AlchemyProxy):
    __tablename__ = "remote"
    
    id = Column(Integer, unique=True, primary_key=True, autoincrement=True)
    server_url = Column(String, unique=True)
    name = Column(String)
    
    @classmethod  # query
    def create(cls, server_url, name, session=None):
        
        # pylint: disable=too-many-arguments
        session = session or relational.session

        remote = cls.t
        if(len(session.query(Remote.m).filter(Remote.m.server_url == server_url).all()) > 0): return remote
        result = session.execute(
            remote.insert(),
            {"server_url": server_url, "name" : name})

        session.commit()
        return remote