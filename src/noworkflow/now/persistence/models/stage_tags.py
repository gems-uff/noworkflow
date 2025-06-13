# Copyright (c) 2016 Universidade Federal Fluminense (UFF)
# Copyright (c) 2016 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""File Access Model"""
from __future__ import (absolute_import, print_function,
                        division, unicode_literals)

import os

from datetime import timedelta
from sqlalchemy import Column, Integer, String, Text, Float
from sqlalchemy import PrimaryKeyConstraint, ForeignKeyConstraint

from ...utils.prolog import PrologDescription, PrologTrial, PrologAttribute
from ...utils.prolog import PrologRepr, PrologTimestamp, PrologNullable
from ...utils.prolog import PrologNullableRepr

from .. import relational

from .base import AlchemyProxy, proxy_class, proxy


@proxy_class
class StageTags(AlchemyProxy):
    """Represent a stage tag mark
    
    TODO
    """

    hide_timestamp = False

    __tablename__ = "stage_tags"
    __table_args__ = (
        PrimaryKeyConstraint("trial_id", "id"),
        ForeignKeyConstraint(["trial_id", "activation_id"],
                             ["activation.trial_id",
                              "activation.id"], ondelete="CASCADE"),
        ForeignKeyConstraint(["trial_id"], ["trial.id"], ondelete="CASCADE"),
    )
    trial_id = Column(String, index=True)
    id = Column(Integer, index=True)                                             # pylint: disable=invalid-name
    name = Column(Text)
    tag_name = Column(Text)
    activation_id = Column(Integer, index=True)
    variable_name = Column(Text)
    variable_value = Column(String)

    # Relationship attributes (see relationships.py):
    #   activation: 1 Activation
    #   trial: 1 Trial

    prolog_description = PrologDescription("access", (
        PrologTrial("trial_id", link="activation.trial_id"),
        PrologAttribute("id", fn=lambda obj: "f{}".format(obj.id)),
        PrologRepr("name"),
        PrologRepr("tag_name"),
        PrologNullable("activation_id", link="activation.id"),
        PrologNullable("variable_name"),
        PrologNullable("variable_value"),
    ), description=(
        "informs that in a given trial (*TrialId*),\n"
        "a file *Id* with *Name* tag function\n"
        "was stamped with the tagging function with\n"
        "*tag_name*. This activation received the *activation_id*."
    ))


    
