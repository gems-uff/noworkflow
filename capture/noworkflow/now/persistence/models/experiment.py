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

from .base import AlchemyProxy, proxy_class, backref_one


def uuid_gen():
    return str(uuid.uuid4())
@proxy_class
class Experiment(AlchemyProxy):
    __tablename__ = "experiment"
    id = Column( 
        String, unique=True, primary_key=True
    )
    name = Column(String, unique=True)
    description = Column(String)

    @classmethod
    def load_experiment(cls,experiment,session=None):
        session = session or relational.session
        return (
            session.query(cls.m)
            .filter((cls.m.name == experiment))
        ).first()
    @classmethod  # query
    def create(cls, expe, session=None):
        
        # pylint: disable=too-many-arguments
        session = session or relational.session

        exp = cls.t
        id=uuid_gen()
        result = session.execute(
            exp.insert(),
            {"id": id, "name": expe.name, "description": expe.description})

        session.commit()
        expe.id=id
        return expe