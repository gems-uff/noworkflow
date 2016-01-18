# Copyright (c) 2016 Universidade Federal Fluminense (UFF)
# Copyright (c) 2016 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""Trial Model"""
from __future__ import (absolute_import, print_function,
                        division, unicode_literals)

import textwrap

from pyposast.cross_version import buffered_str

from future.utils import with_metaclass
from sqlalchemy import Column, Integer, Text, TIMESTAMP
from sqlalchemy import ForeignKeyConstraint, select, func
from sqlalchemy.orm import relationship

from ..formatter import PrettyLines
from ..graphs.trial_graph import TrialGraph
from ..persistence import persistence

from .base import set_proxy
from .trial_prolog import TrialProlog
from .tag import Tag
from .module import Module
from .dependency import Dependency
from .activation import Activation
from .head import Head


class Trial(persistence.base):
    """Trial Table
    Store trials
    """
    __tablename__ = "trial"
    __table_args__ = (
        ForeignKeyConstraint(["inherited_id"], ["trial.id"],
                             ondelete="RESTRICT"),
        ForeignKeyConstraint(["parent_id"], ["trial.id"], ondelete="SET NULL"),
        {"sqlite_autoincrement": True},
    )
    id = Column(Integer, primary_key=True)
    start = Column(TIMESTAMP)
    finish = Column(TIMESTAMP)
    script = Column("script", Text)
    code_hash = Column("code_hash", Text)
    arguments = Column(Text)
    command = Column(Text)
    inherited_id = Column(Integer, index=True)
    parent_id = Column(Integer, index=True)
    run = Column(Integer)

    inherited = relationship(
        "Trial", backref="bypass_children", viewonly=True,
        remote_side=[id], primaryjoin=(id == inherited_id))


    parent = relationship(
        "Trial", backref="children", viewonly=True,
        remote_side=[id], primaryjoin=(id == parent_id))

    #ToDo: check bypass
    function_defs = relationship(
        "FunctionDef", lazy="dynamic", backref="trial")
    module_dependencies = relationship(
        "Dependency", lazy="dynamic", backref="trials")
    _modules = relationship(
        "Module", secondary=Dependency.__table__, lazy="dynamic",
        backref="trials")
    environment_attrs = relationship(
        "EnvironmentAttr", lazy="dynamic", backref="trial")
    activations = relationship(
        "Activation", lazy="dynamic", order_by=Activation.start,
        backref="trial")
    file_accesses = relationship(
        "FileAccess", lazy="dynamic", backref="trial", viewonly=True)
    object_values = relationship(
        "ObjectValue", lazy="dynamic", backref="trial", viewonly=True)

    slicing_variables = relationship(
        "SlicingVariable", lazy="dynamic", backref="trial", viewonly=True)
    slicing_usages = relationship(
        "SlicingUsage", lazy="dynamic", viewonly=True, backref="trial")
    slicing_dependencies = relationship(
        "SlicingDependency", lazy="dynamic", viewonly=True, backref="trial")

    tags = relationship(
        "Tag", lazy="dynamic", backref="trial")

    # bypass_children: Trial.inherited backref
    # children: Trial.parent backref

    @classmethod
    def last_trial(cls, script=None, parent_required=False, session=None):
        """Return last trial according to start time

        Keyword arguments:
        script -- specify the desired script (default=None)
        parent_required -- valid only if script exists (default=False)
        """
        session = session or persistence.session
        trial = (
            session.query(cls)
            .filter(cls.start.in_(
                select([func.max(cls.start)])
                .where(cls.script == script)
            ))
        ).first()
        if trial or parent_required:
            return trial
        return (
            persistence.session.query(cls)
            .filter(cls.start.in_(
                select([func.max(cls.start)])
            ))
        ).first()

    @classmethod
    def load_trial(cls, trial_ref, session=None):
        """Load trial by trial reference

        Find reference on trials id and tags name
        """
        session = session or persistence.session
        return (
            session.query(cls)
            .outerjoin(Tag)
            .filter((cls.id == trial_ref) | (Tag.name == trial_ref))
        ).first()

    @classmethod
    def load_parent(cls, script, remove=True, parent_required=False, session=None):
        """Load head trial by script


        Keyword arguments:
        remove -- remove from head, after loading (default=True)
        parent_required -- valid only if script exists (default=False)
        session -- specify session for loading (default=persistence.session)
        """
        session = session or persistence.session
        head = Head.load_head(script, session=session)
        if head:
            trial = head.trial
            if remove:
                session.expunge(head)
                remove_session = persistence.make_session()
                remove_session.delete(head)
                #remove_session.merge(head, load=False)
                #head.delete()
                remove_session.commit()
        elif not head:
            trial = cls.last_trial(
                script=script, parent_required=parent_required,
                session=session)
        return trial

    def create_head(self):
        """Create head for this trial"""
        session = persistence.make_session()
        session.query(Head).filter(Head.script == self.script).delete()
        session.add(Head(trial_id=self.id, script=self.script))
        session.commit()

    @property
    def script_content(self):
        """Return the "main" script content of the trial"""
        return PrettyLines(
            buffered_str(persistence.get(self.code_hash)).split("/n"))

    @property
    def finished(self):
        """Check if trial has finished"""
        return bool(self.finish)

    @property
    def status(self):
        """Check trial status
        Possible statuses: finished, unfinished, backup"""
        if not self.run:
            return "backup"
        return "finished" if self.finished else "unfinished"

    @property
    def duration(self):
        """Calculate trial duration"""
        if self.finish:
            return int((self.finish - self.start).total_seconds() * 1000000)
        return 0

    @property
    def local_modules(self):
        """Load local modules
        Return SQLAlchemy query"""
        return self.modules.filter(
            Module.path.like("%{}%".format(persistence.base_path)))

    @property
    def modules(self):
        """Load modules
        Return SQLAlchemy query"""
        if self.inherited:
            return self.inherited.modules
        return self._modules

    @classmethod
    def to_prolog_fact(cls):
        """Return prolog comment"""
        return textwrap.dedent("""
            %
            % FACT: trial(trial_id).
            %
            """)

    @classmethod
    def to_prolog_dynamic(cls):
        """Return prolog dynamic clause"""
        return ":- dynamic(trial/1)."

    @classmethod
    def to_prolog_retract(cls, trial_id):
        """Return prolog retract for trial"""
        return "retract(trial({}))".format(trial_id)

    @classmethod
    def empty_prolog(self):
        """Return empty prolog fact"""
        return "trial(0)."


    def to_prolog(self):
        """Convert to prolog fact"""
        return (
            "trial({t.id})."
        ).format(t=self)

    def show(self, _print=lambda x: print(x)):
        """Print trial information"""
        _print("""\
            Id: {t.id}
            Inherited Id: {t.inherited_id}
            Script: {t.script}
            Code hash: {t.code_hash}
            Start: {t.start}
            Finish: {t.finish}
            Duration: {t.duration} ms\
            """.format(t=self))

    def __repr__(self):
        return "Trial({})".format(self.id)


class TrialProxy(with_metaclass(set_proxy(Trial))):
    """This model represents a trial
    Initialize it by passing a trial reference:
        trial = Trial(2)


    There are four visualization modes for the graph:
        tree: activation tree without any filters
            trial.graph.mode = 0
        no match: tree transformed into a graph by the addition of sequence and
                  return edges and removal of intermediate call edges
            trial.graph.mode = 1
        exact match: calls are only combined when all the sub-call match
            trial.graph.mode = 2
        namesapce: calls are combined without considering the sub-calls
            trial.graph.mode = 3


    You can change the graph width and height by the variables:
        trial.graph.width = 600
        trial.graph.height = 400
    """


    DEFAULT = {
        "graph.width": 500,
        "graph.height": 500,
        "graph.mode": 3,
        "graph.use_cache": True,
        "prolog.use_cache": True,
    }

    REPLACE = {
        "graph_width": "graph.width",
        "graph_height": "graph.height",
        "graph_mode": "graph.mode",
        "graph_use_cache": "graph.use_cache",
        "prolog_use_cache": "prolog.use_cache",
    }

    def __init__(self, *args, **kwargs):
        if args and isinstance(args[0], persistence.base):
            obj = args[0]
            self._alchemy = obj
            self._store_pk()
        elif args:
            trial_ref = kwargs.get("trial_ref", args[0])
        else:
            trial_ref = kwargs.get("trial_ref", None)

        # Check if it is a new trial or a query
        script = kwargs.get("trial_script", None)
        if 'use_cache' in kwargs:
            cache = kwargs['use_cache']
            kwargs['graph_use_cache'] = kwargs.get('graph_use_cache', cache)
            kwargs['prolog_use_cache'] = kwargs.get('graph_use_cache', cache)


        session = persistence.session
        if not trial_ref or trial_ref == -1:
            self._alchemy = Trial.last_trial(script=script, session=session)
            if 'graph_use_cache' not in kwargs:
                kwargs['graph_use_cache'] = False
            if 'prolog_use_cache' not in kwargs:
                kwargs['prolog_use_cache'] = False
        else:
            self._alchemy = Trial.load_trial(trial_ref, session=session)


        if self._alchemy is None:
            raise RuntimeError("Trial {} not found".format(trial_ref))
        self._store_pk()

        self.graph = TrialGraph(self)
        self.prolog = TrialProlog(self)
        self.initialize_default(kwargs)


    def query(self, query):
        """Run prolog query"""
        return self.prolog.query(query)

    def prolog_rules(self):
        """Return prolog rules"""
        return self.prolog.export_rules()

    def _repr_html_(self):
        """Display d3 graph on ipython notebook"""
        if hasattr(self, "graph"):
            return self.graph._repr_html_()
        return repr(self)
