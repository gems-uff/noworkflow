# Copyright (c) 2016 Universidade Federal Fluminense (UFF)
# Copyright (c) 2016 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""Tag Model"""
from __future__ import (absolute_import, print_function,
                        division, unicode_literals)

from datetime import datetime

import uuid
from future.utils import lmap
from future.builtins import map as cvmap
from sqlalchemy import Column, Integer, String, Text, TIMESTAMP
from sqlalchemy import ForeignKeyConstraint, select, bindparam

from ...utils.prolog import PrologDescription, PrologTrial
from ...utils.prolog import PrologRepr, PrologTimestamp

from .. import relational

from .base import AlchemyProxy, proxy_class


def uuid_gen():
    return str(uuid.uuid4())
@proxy_class
class MemberOfGroup(AlchemyProxy):
    __tablename__ = "memberOfGroup"
    __table_args__ = (
      
        ForeignKeyConstraint(["userId"],
                             ["user.id"], ondelete="CASCADE"),
        ForeignKeyConstraint(["groupId"],
                             ["group.id"], ondelete="CASCADE")
    )
    id = Column( 
        String, unique=True, primary_key=True
    )
    userId = Column(Text)
    groupId = Column(Text)
    

    
    @classmethod  # query
    def create(cls, UsrGrp, session=None):
        
        # pylint: disable=too-many-arguments
        session = session or relational.session

        UsrGrop = cls.t
        id=uuid_gen()
        result = session.execute(
            UsrGrop.insert(),
            {"id": id, "userId": UsrGrp.userId, "groupId": UsrGrp.groupId})

        session.commit()
        UsrGrp.id=id
        return UsrGrp