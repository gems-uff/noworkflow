# Copyright (c) 2016 Universidade Federal Fluminense (UFF)
# Copyright (c) 2016 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""Trial Model"""
from __future__ import (absolute_import, print_function,
                        division, unicode_literals)

import sys
from pyposast.cross_version import buffered_str

from sqlalchemy import Column, Integer, Text, TIMESTAMP
from sqlalchemy import ForeignKeyConstraint
from sqlalchemy.orm import relationship

from ..formatter import PrettyLines
from ..utils import print_msg
from ..graphs.trial_graph import TrialGraph
from ..persistence import persistence
from .model import Model
from .trial_prolog import TrialProlog

from .module import Module
from .dependency import Dependency
from .activation import Activation


class Trial(Model, persistence.base):
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

    DEFAULT = {
        "graph.width": 500,
        "graph.height": 500,
        "graph.mode": 3,
        "use_cache": True,
    }

    REPLACE = {
        "graph_width": "graph.width",
        "graph_height": "graph.height",
        "graph_mode": "graph.mode",
    }

    def __new__(cls, *args, **kwargs):
        # Check if it is a new trial or a query
        trial_ref = kwargs.get("trial_ref", None)
        script = kwargs.get("script", None)
        if args and not trial_ref:
            trial_ref = args[0]

        if trial_ref or script:
            use_cache = True
            if not trial_ref:
                trial_ref = persistence.last_trial_id(script=script)
                use_cache = False

            trial_id = persistence.load_trial_id(trial_ref)

            if trial_id is None:
                return None

            trial = persistence.session.query(cls).get(trial_id)

            trial.use_cache = use_cache
            trial._info = None
            trial.graph = TrialGraph(trial_id)
            trial.initialize_default(kwargs)
            trial.graph.use_cache = trial.use_cache
            trial.trial_prolog = TrialProlog(trial)

            return trial

        return super(Trial, cls).__new__(cls, *args, **kwargs)

    def query(self, query):
        """Run prolog query"""
        return self.trial_prolog.query(query)

    def prolog_rules(self):
        """Return prolog rules"""
        return self.trial_prolog.export_rules()

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

    def _repr_html_(self):
        """Display d3 graph on ipython notebook"""
        return self.graph._repr_html_(self)

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
