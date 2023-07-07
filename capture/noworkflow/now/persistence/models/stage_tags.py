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

    # Relationship attributes (see relationships.py):
    #   activation: 1 Activation
    #   trial: 1 Trial

    prolog_description = PrologDescription("access", (
        PrologTrial("trial_id", link="activation.trial_id"),
        PrologAttribute("id", fn=lambda obj: "f{}".format(obj.id)),
        PrologRepr("name"),
        PrologRepr("tag_name"),
        PrologNullable("activation_id", link="activation.id"),
    ), description=(
        "informs that in a given trial (*TrialId*),\n"
        "a file *Id* with *Name* tag function\n"
        "was stamped with the tagging function with\n"
        "*tag_name*. This activation received the *activation_id*."
    ))

    @property
    def timestamp(self):
        """Return activation finish time
        
        Doctest:
         >>> from noworkflow.tests.helpers.models import new_trial, TrialConfig
        >>> from noworkflow.tests.helpers.models import AccessConfig
        >>> from noworkflow.now.persistence.models import Activation
        >>> access_config = AccessConfig(read_timestamp=3)
        >>> config = TrialConfig("finished")
        >>> trial_id = new_trial(config, access=access_config, erase=True)
        >>> access = FileAccess((trial_id, access_config.r_access.id))

        Return access timestamp:
        >>> access.timestamp == config.trial_start + timedelta(seconds=3)
        True
        """
        return self.trial.start + timedelta(seconds=self.checkpoint)

    @property
    def stack(self):
        """Return the activation stack since the beginning of execution


        Doctest:
        >>> from noworkflow.tests.helpers.models import new_trial, TrialConfig
        >>> from noworkflow.tests.helpers.models import AccessConfig
        >>> from noworkflow.now.persistence.models import Activation
        >>> access_config = AccessConfig(read_file="a.txt", read_hash="ab")
        >>> trial_id = new_trial(TrialConfig("finished"),
        ...                      access=access_config, erase=True)
        >>> access = FileAccess((trial_id, access_config.r_access.id))

        Return activation stack:
        >>> access.stack == 'f -> ... -> open'
        True
        """
        stack = []
        activation = self.activation
        while activation:
            name = activation.name
            activation = activation.caller
            if activation:
                stack.insert(0, name)
        if not stack or stack[-1] != "open":
            stack.append("... -> open")
        return " -> ".join(stack)

    @property
    def brief(self):
        """Brief description of file access


        Doctest:
        >>> from noworkflow.tests.helpers.models import new_trial, TrialConfig
        >>> from noworkflow.tests.helpers.models import AccessConfig
        >>> from noworkflow.now.persistence.models import Activation
        >>> access_config = AccessConfig(
        ...     read_file="a.txt", read_hash="ab", write_file="b.txt",
        ...     write_hash_before=None)
        >>> trial_id = new_trial(TrialConfig("finished"),
        ...                      access=access_config, erase=True)

        Show mode and name:
        >>> (FileAccess((trial_id, access_config.r_access.id)).brief
        ... ) == '(r) a.txt'
        True

        Indicate new files:
        >>> (FileAccess((trial_id, access_config.w_access.id)).brief
        ... ) == '(w) b.txt (new)'
        True
        """
        result = "({0.mode}) {0.name}".format(self)
        if self.content_hash_before is None:
            result += " (new)"
        return result

    @property
    def is_internal(self):
        """Check if file access is inside trial project


        Doctest:
        >>> from noworkflow.tests.helpers.models import new_trial, TrialConfig
        >>> from noworkflow.tests.helpers.models import AccessConfig
        >>> from noworkflow.now.persistence.models import Activation
        >>> access_config = AccessConfig(
        ...     read_file="a.txt", read_hash="ab", write_file="/x/b.txt",
        ...     write_hash_before=None)
        >>> trial_id = new_trial(TrialConfig("finished"),
        ...                      access=access_config, erase=True)

        Show mode and name:
        >>> FileAccess((trial_id, access_config.r_access.id)).is_internal
        True

        Indicate new files:
        >>> FileAccess((trial_id, access_config.w_access.id)).is_internal
        False
        """
        return (
            (not os.path.isabs(self.name)) or
            self.trial.path in self.name
        )

    @classmethod  # query
    def find_by_name_and_time(cls, name, timestamp, trial=None, session=None):
        """Return the first access according to name and timestamp

        Arguments:
        name -- specify the desired file
        checkpoint -- specify the start of finish time of trial

        Keyword Arguments:
        trial -- limit search in a specific trial_id


        Doctest:
        >>> from datetime import datetime
        >>> from noworkflow.tests.helpers.models import new_trial, TrialConfig
        >>> from noworkflow.tests.helpers.models import AccessConfig
        >>> from noworkflow.tests.helpers.models import AssignConfig
        >>> from noworkflow.now.persistence.models import Activation
        >>> access_config = AccessConfig(
        ...     read_file="a.txt", read_hash="ab", write_file="a.txt",
        ...     write_hash_before=None,
        ...     read_timestamp=4199751.0, # 2016-05-26 15:53:51
        ...     write_timestamp=1607455.0, # 2016-04-26 15:48:55
        ... )
        >>> trial_id = new_trial(TrialConfig("finished"),
        ...                      access=access_config, erase=True)

        Find accesses by name and checkpoint:
        >>> FileAccess.find_by_name_and_time(
        ... 'a.txt', '2016-04-26 15:48:55')  # doctest: +ELLIPSIS
        access(..., ..., 'a.txt', 'w', nil, 'b', ..., ...).

        Find accesses by name and partial checkpoint:
        >>> FileAccess.find_by_name_and_time(
        ... 'a.txt', '2016-05') # doctest: +ELLIPSIS
        access(..., ..., 'a.txt', 'r', 'ab', 'ab', ..., ...).

        Return None if not found:
        >>> FileAccess.find_by_name_and_time(
        ... 'a.txt', '2017') # doctest: +ELLIPSIS
        """
        model = cls.m
        session = session or relational.session
        query = (
            session.query(model)
            .filter(
                (model.name == name)
                # &(model.checkpoint.like(checkpoint + "%"))
            ).order_by(model.checkpoint)
        )
        if trial:
            query = query.filter(model.trial_id == trial)
        for access in query:
            paccess = proxy(access)
            if str(paccess.timestamp).startswith(timestamp):
                return paccess
        return None

    def __key(self):
        return (self.name, self.content_hash_before, self.content_hash_after,
                self.mode)

    def __hash__(self):
        return hash(self.__key())

    def __eq__(self, other):
        if not isinstance(other, FileAccess):
            return False
        return (
            (self.content_hash_before == other.content_hash_before)
            and (self.content_hash_after == other.content_hash_after)
        )

    def show(self, print_=print):
        """Show file access

        Keyword arguments:
        print_ -- custom print function (default=print)


        Doctest:
        >>> from datetime import datetime
        >>> from textwrap import dedent
        >>> from noworkflow.tests.helpers.models import new_trial, TrialConfig
        >>> from noworkflow.tests.helpers.models import AccessConfig
        >>> from noworkflow.now.persistence.models import Activation
        >>> access_config = AccessConfig(
        ...     read_file="a.txt", read_hash="ab",
        ...     read_timestamp=4199751.0) # 2016-05-26 15:53:51
        >>> trial_id = new_trial(TrialConfig("finished"),
        ...                      access=access_config, erase=True)

        Show FileAccess:
        >>> FileAccess((trial_id, access_config.r_access.id)).show(
        ...     print_=lambda x: print(dedent(x))
        ... )  #doctest: +ELLIPSIS +NORMALIZE_WHITESPACE
        Name: a.txt
        Mode: r
        Buffering: default
        Content hash before: ab
        Content hash after: ab
        Timestamp: 2016-05-26 15:53:51
        Function: f -> ... -> open
        """
        result = """\
            Name: {f.name}
            Mode: {f.mode}
            Buffering: {f.buffering}
            Content hash before: {f.content_hash_before}
            Content hash after: {f.content_hash_after}
            """
        if not self.hide_timestamp:
            result += """Timestamp: {f.timestamp}
            """
        result += """Function: {f.stack}\
            """
        print_(result.format(f=self))



class UniqueFileAccess(StageTags):
    """FileAccess with Unique hash"""

    def __key(self):
        return self.id

    def __eq__(self, other):
        if not isinstance(other, StageTags):
            return False
        return self.id == other.id

    def __hash__(self):
        return hash(self.__key())

    def resolve_node(self, clusterizer, cluster, nid):
        """Resolve node for clusterizer"""
        fcluster = clusterizer.main_cluster
        if not self.is_internal:
            fcluster = cluster
        return fcluster, nid
