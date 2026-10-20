# Copyright (c) 2016 Universidade Federal Fluminense (UFF)
# Copyright (c) 2016 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""Tag Model"""
from __future__ import absolute_import, division, print_function, unicode_literals

import uuid

from sqlalchemy import Column, String

from ...utils.prolog import PrologDescription, PrologRepr
from .. import relational
from .base import AlchemyProxy, proxy_class


def uuid_gen():
    return str(uuid.uuid4())
@proxy_class
class Group(AlchemyProxy):
    __tablename__ = "group"
    id = Column( 
        String, unique=True, primary_key=True
    )
    name = Column(String, unique=True)
    
    prolog_description = PrologDescription("group", (
        PrologRepr("id"),
        PrologRepr("name"),
    ), description=(
        "informs that a group (*Id*)\n"
        "has a *Name*."
    ))

    @classmethod  # query
    def create(cls, grp, session=None):
        
        # pylint: disable=too-many-arguments
        session = session or relational.session

        grop = cls.t
        id=uuid_gen()
        session.execute(
            grop.insert(),
            {"id": id, "name": grp.name})

        session.commit()
        grp.id=id
        return grp
    @classmethod  # query
    def delete(cls, grpId, session=None):

        # pylint: disable=too-many-arguments
        session = session or relational.session

        model=cls.m
        session = session or relational.session

        session.query(model).filter(model.id==grpId).delete()
        session.commit()