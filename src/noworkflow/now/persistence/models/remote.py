# Copyright (c) 2016 Universidade Federal Fluminense (UFF)
# Copyright (c) 2016 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""Remote Model"""
from __future__ import (absolute_import, print_function,
                        division, unicode_literals)

from future.utils import lmap
from future.builtins import map as cvmap
from sqlalchemy import Column, String, Integer, Boolean

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
    used = Column(Boolean)
    hide = Column(Boolean)
    
    @classmethod  # query
    def create(cls, server_url, name, used=False, hide=False, session=None):
        
        # pylint: disable=too-many-arguments
        session = session or relational.session

        remote = cls.t
        
        remote_in_db = session.query(Remote.m).filter(Remote.m.server_url == server_url).all()
        if(len(remote_in_db) > 0):
            if remote_in_db[0].used == False or remote_in_db[0].used == 0:
                remote_in_db[0].used = True
                relational.session.commit()
            return remote
        
        result = session.execute(
            remote.insert(),
            {"server_url": server_url, "name" : name, "used" : used, "hide": False})

        session.commit()
        return remote