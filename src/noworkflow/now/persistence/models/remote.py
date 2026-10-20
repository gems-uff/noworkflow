# Copyright (c) 2016 Universidade Federal Fluminense (UFF)
# Copyright (c) 2016 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""Remote Model"""

from __future__ import absolute_import, division, print_function, unicode_literals

from sqlalchemy import Boolean, Column, Integer, String

from ...utils.prolog import (
    PrologAttribute,
    PrologBoolean,
    PrologDescription,
    PrologRepr,
)
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

    prolog_description = PrologDescription(
        "remote",
        (
            PrologAttribute("id"),
            PrologRepr("server_url"),
            PrologRepr("name"),
            PrologBoolean("used"),
            PrologBoolean("hide"),
        ),
        description=(
            "informs that a remote server (*Id*)\n"
            "has a *ServerUrl* and *Name*,\n"
            "with *Used* and *Hide* flags."
        ),
    )

    @classmethod  # query
    def create(cls, server_url, name, used=False, hide=False, session=None):

        # pylint: disable=too-many-arguments
        session = session or relational.session

        remote = cls.t

        remote_in_db = (
            session.query(Remote.m).filter(Remote.m.server_url == server_url).all()
        )
        if len(remote_in_db) > 0:
            if remote_in_db[0].used == 0:
                remote_in_db[0].used = True
                relational.session.commit()
            return remote

        session.execute(
            remote.insert(),
            {"server_url": server_url, "name": name, "used": used, "hide": False},
        )

        session.commit()
        return remote
