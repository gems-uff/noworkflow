# Copyright (c) 2016 Universidade Federal Fluminense (UFF)
# Copyright (c) 2016 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""File Access Model"""
from __future__ import (absolute_import, print_function,
                        division, unicode_literals)

import os

from sqlalchemy import Column, Integer, Text, TIMESTAMP
from sqlalchemy import PrimaryKeyConstraint, ForeignKeyConstraint

from ...utils.prolog import PrologDescription, PrologTrial, PrologAttribute
from ...utils.prolog import PrologRepr, PrologTimestamp, PrologNullable
from ...utils.prolog import PrologNullableRepr

from .. import relational

from .base import AlchemyProxy, proxy_class, backref_one, proxy


@proxy_class
class FileAccess(AlchemyProxy):
    """Represent a file access


    Doctest:
    >>> from noworkflow.tests.helpers.models import new_trial, TrialConfig
    >>> from noworkflow.tests.helpers.models import AccessConfig, AssignConfig
    >>> from noworkflow.now.persistence.models import Activation
    >>> assign = AssignConfig(arg="a")
    >>> access_config = AccessConfig(read_file="a.txt", read_hash="ab")
    >>> trial_id = new_trial(TrialConfig("finished"), assignment=assign,
    ...                      access=access_config, erase=True)
    >>> f_activation = Activation((trial_id, assign.f_activation))

    Load FileAccess by (trial_id, id):
    >>> access = FileAccess((trial_id, access_config.r_access.id))
    >>> access  # doctest: +ELLIPSIS
    access(..., ..., 'a.txt', 'r', 'ab', 'ab', ..., ...).

    Load FileAccess trial:
    >>> access.trial.id == trial_id
    True

    Load FileAccess activation:
    >>> access.activation.id == f_activation.id
    True
    """

    hide_timestamp = False

    __tablename__ = "file_access"
    __table_args__ = (
        PrimaryKeyConstraint("trial_id", "id"),
        ForeignKeyConstraint(["trial_id", "activation_id"],
                             ["activation.trial_id",
                              "activation.id"], ondelete="CASCADE"),
        ForeignKeyConstraint(["trial_id"], ["trial.id"], ondelete="CASCADE"),
    )
    trial_id = Column(Integer, index=True)
    id = Column(Integer, index=True)                                             # pylint: disable=invalid-name
    name = Column(Text)
    mode = Column(Text)
    buffering = Column(Text)
    content_hash_before = Column(Text)
    content_hash_after = Column(Text)
    timestamp = Column(TIMESTAMP)
    activation_id = Column(Integer, index=True)

    trial = backref_one("trial")  # Trial.file_accesses
    activation = backref_one("activation")  # Activation.file_accesses

    prolog_description = PrologDescription("access", (
        PrologTrial("trial_id", link="activation.trial_id"),
        PrologAttribute("id", fn=lambda obj: "f{}".format(obj.id)),
        PrologRepr("name"),
        PrologRepr("mode"),
        PrologNullableRepr("content_hash_before"),
        PrologNullableRepr("content_hash_after"),
        PrologTimestamp("timestamp"),
        PrologNullable("activation_id", link="activation.id"),
    ), description=(
        "informs that in a given trial (*TrialId*),\n"
        "a file *Id* with *Name*\n"
        "was accessed in a specific read or write *Mode*\n"
        "The content of the file\n"
        "was captured before (*ContentHashBefore*)\n"
        "and after (*ContentHashAfter*) the access."
        "The file was accessed at a specific *Timestamp*\n"
        "by a function activation (*ActivationId*)."
    ))

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
        timestamp -- specify the start of finish time of trial

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
        ...     read_timestamp=datetime(year=2016, month=5, day=26,
        ...                              hour=15, minute=53, second=51),
        ...     write_timestamp=datetime(year=2016, month=4, day=26,
        ...                              hour=15, minute=48, second=55))
        >>> trial_id = new_trial(TrialConfig("finished"),
        ...                      access=access_config, erase=True)

        Find accesses by name and timestamp:
        >>> FileAccess.find_by_name_and_time(
        ... 'a.txt', '2016-04-26 15:48:55')  # doctest: +ELLIPSIS
        access(..., ..., 'a.txt', 'w', nil, 'b', ..., ...).

        Find accesses by name and partial timestamp:
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
                (model.name == name) &
                (model.timestamp.like(timestamp + "%"))
            ).order_by(model.timestamp)
        )
        if trial:
            query = query.filter(model.trial_id == trial)
        return proxy(query.first())

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
        ...     read_timestamp=datetime(year=2016, month=5, day=26,
        ...                              hour=15, minute=53, second=51))
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



class UniqueFileAccess(FileAccess):
    """FileAccess with Unique hash"""

    def __key(self):
        return self.id

    def __eq__(self, other):
        if not isinstance(other, FileAccess):
            return False
        return self.id == other.id

    def __hash__(self):
        return hash(self.__key())

    def resolve_node(self, clusterizer, cluster, nid):
        """Resolve node for clusterizer"""
        fcluster = clusterizer.main_cluster
        if not self.is_internal:
            fcluster = cluster
        return cluster, nid
