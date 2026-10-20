# Copyright (c) 2016 Universidade Federal Fluminense (UFF)
# Copyright (c) 2016 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""Tag Model"""
from __future__ import absolute_import, division, print_function, unicode_literals

import uuid

from sqlalchemy import Column, ForeignKeyConstraint, String, Text

from ...utils.prolog import PrologDescription, PrologRepr
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
    
    prolog_description = PrologDescription("memberOfGroup", (
        PrologRepr("id"),
        PrologRepr("userId"),
        PrologRepr("groupId"),
    ), description=(
        "informs that a user (*UserId*)\n"
        "is a member of group (*GroupId*)."
    ))

    @classmethod  # query
    def create(cls, UsrGrp, session=None):
        
        # pylint: disable=too-many-arguments
        session = session or relational.session

        UsrGrop = cls.t
        id=uuid_gen()
        session.execute(
            UsrGrop.insert(),
            {"id": id, "userId": UsrGrp.userId, "groupId": UsrGrp.groupId})

        session.commit()
        UsrGrp.id=id
        return UsrGrp