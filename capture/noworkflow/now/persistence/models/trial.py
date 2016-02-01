# Copyright (c) 2016 Universidade Federal Fluminense (UFF)
# Copyright (c) 2016 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""Trial Model"""
from __future__ import (absolute_import, print_function,
                        division, unicode_literals)

import textwrap

from pyposast import native_decode_source

from future.utils import with_metaclass
from sqlalchemy import Column, Integer, Text, TIMESTAMP
from sqlalchemy import ForeignKeyConstraint, select, func
from sqlalchemy.orm import relationship

from ...utils.formatter import PrettyLines

from .. import relational, content, persistence_config

from .base import set_proxy, proxy_gen, proxy_attr, proxy_method
from .trial_prolog import TrialProlog
from .tag import Tag
from .module import Module
from .dependency import Dependency
from .activation import Activation
from .head import Head, HeadProxy
from .graphs.trial_graph import TrialGraph


class Trial(relational.base):
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
    script = Column(Text)
    code_hash = Column(Text)
    arguments = Column(Text)
    command = Column(Text)
    inherited_id = Column(Integer, index=True)
    parent_id = Column(Integer, index=True)
    run = Column(Integer)

    _inherited = relationship(
        "Trial", backref="_bypass_children", viewonly=True,
        remote_side=[id], primaryjoin=(id == inherited_id))

    _parent = relationship(
        "Trial", backref="_children", viewonly=True,
        remote_side=[id], primaryjoin=(id == parent_id))

    _function_defs = relationship(
        "FunctionDef", lazy="dynamic", backref="_trial")
    _module_dependencies = relationship(
        "Dependency", lazy="dynamic", backref="_trials")
    _modules = relationship(
        "Module", secondary=Dependency.__table__, lazy="dynamic",
        backref="_trials")
    _environment_attrs = relationship(
        "EnvironmentAttr", lazy="dynamic", backref="_trial")
    _activations = relationship(
        "Activation", lazy="dynamic", order_by=Activation.start,
        backref="_trial")
    _file_accesses = relationship(
        "FileAccess", lazy="dynamic", backref="_trial", viewonly=True)
    _objects = relationship(
        "Object", lazy="dynamic", backref="_trial", viewonly=True)
    _object_values = relationship(
        "ObjectValue", lazy="dynamic", backref="_trial", viewonly=True)

    _slicing_variables = relationship(
        "SlicingVariable", lazy="dynamic", backref="_trial", viewonly=True)
    _slicing_usages = relationship(
        "SlicingUsage", lazy="dynamic", viewonly=True, backref="_trial")
    _slicing_dependencies = relationship(
        "SlicingDependency", lazy="dynamic", viewonly=True, backref="_trial")

    _tags = relationship(
        "Tag", lazy="dynamic", backref="_trial")

    # _bypass_children: Trial._inherited backref
    # _children: Trial._parent backref

    @property
    def _query_local_modules(self):
        """Load local modules
        Return SQLAlchemy query"""
        return self._query_modules.filter(
            Module.path.like("%{}%".format(persistence_config.base_path)))

    @property
    def _query_modules(self):
        """Load modules
        Return SQLAlchemy query"""
        if self._inherited:
            return self._inherited._query_modules
        return self._modules

    @property
    def _query_initial_activations(self):
        """Return initial activation as a SQLAlchemy query"""
        return self._activations.filter(Activation.caller_id == None)


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

    local_modules = proxy_attr("_query_local_modules", proxy=proxy_gen)
    activations = proxy_attr("_activations", proxy=proxy_gen)
    modules = proxy_attr("_query_modules", proxy=proxy_gen)
    environment_attrs = proxy_attr("_environment_attrs", proxy=proxy_gen)
    file_accesses = proxy_attr("_file_accesses", proxy=proxy_gen)
    function_defs = proxy_attr("_function_defs", proxy=proxy_gen)
    slicing_variables = proxy_attr("_slicing_variables", proxy=proxy_gen)
    slicing_usages = proxy_attr("_slicing_usages", proxy=proxy_gen)
    slicing_dependencies = proxy_attr("_slicing_dependencies", proxy=proxy_gen)
    initial_activations = proxy_attr("_query_initial_activations",
                                     proxy=proxy_gen)
    tags = proxy_attr("_tags", proxy=proxy_gen)

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
        if args and isinstance(args[0], relational.base):
            obj = args[0]
            trial_ref = obj.id
        elif args:
            trial_ref = kwargs.get("trial_ref", args[0])
        else:
            trial_ref = kwargs.get("trial_ref", None)

        # Check if it is a new trial or a query
        script = kwargs.get("trial_script", None)
        if "use_cache" in kwargs:
            cache = kwargs["use_cache"]
            kwargs["graph_use_cache"] = kwargs.get("graph_use_cache", cache)
            kwargs["prolog_use_cache"] = kwargs.get("graph_use_cache", cache)

        session = relational.session
        if not trial_ref or trial_ref == -1:
            obj = TrialProxy.last_trial(script=script, session=session)
            if "graph_use_cache" not in kwargs:
                kwargs["graph_use_cache"] = False
            if "prolog_use_cache" not in kwargs:
                kwargs["prolog_use_cache"] = False
        else:
            obj = TrialProxy.load_trial(trial_ref, session=session)

        if obj is None:
            raise RuntimeError("Trial {} not found".format(trial_ref))
        self._store_pk(obj)
        self._restore_instance()

        self.graph = TrialGraph(self)
        self.prolog = TrialProlog(self)
        self.initialize_default(kwargs)

    @property
    def script_content(self):
        """Return the "main" script content of the trial"""
        return PrettyLines(
            native_decode_source(content.get(self.code_hash)).split("/n"))

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
        """Calculate trial duration. Return microseconds"""
        if self.finish:
            return int((self.finish - self.start).total_seconds() * 1000000)
        return 0

    @property
    def duration_text(self):
        """Calculate trial duration. Return formatted str"""
        if self.finish:
            return str(self.finish - self.start)
        return "None"

    @property
    def environment(self):
        """Return dict: environment variables -> value"""
        return {e.name: e.value for e in self.environment_attrs}

    def create_head(self):
        """Create head for this trial"""
        session = relational.make_session()
        session.query(Head).filter(Head.script == self.script).delete()
        session.add(Head(trial_id=self.id, script=self.script))
        session.commit()

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
            Duration: {t.duration_text}\
            """.format(t=self))

    def __repr__(self):
        return "Trial({})".format(self.id)

    @proxy_method
    def last_trial(model, cls, script=None, parent_required=False,
                   session=None):
        """Return last trial according to start time

        Keyword arguments:
        script -- specify the desired script (default=None)
        parent_required -- valid only if script exists (default=False)
        """
        session = session or relational.session
        trial = (
            session.query(model)
            .filter(model.start.in_(
                select([func.max(model.start)])
                .where(model.script == script)
            ))
        ).first()
        if trial or parent_required:
            return trial
        return (
            session.query(model)
            .filter(model.start.in_(
                select([func.max(model.start)])
            ))
        ).first()

    @proxy_method
    def load_trial(model, cls, trial_ref, session=None):
        """Load trial by trial reference

        Find reference on trials id and tags name
        """
        session = session or relational.session
        return (
            session.query(model)
            .outerjoin(Tag)
            .filter((model.id == trial_ref) | (Tag.name == trial_ref))
        ).first()

    @proxy_method
    def load_parent(model, cls, script, remove=True, parent_required=False,
                    session=None):
        """Load head trial by script


        Keyword arguments:
        remove -- remove from head, after loading (default=True)
        parent_required -- valid only if script exists (default=False)
        session -- specify session for loading (default=relational.session)
        """
        session = session or relational.session
        head = HeadProxy.load_head(script, session=session)
        if head:
            trial = head.trial
            if remove:
                HeadProxy.remove(head.id, session=relational.make_session())
        elif not head:
            trial = cls.last_trial(
                script=script, parent_required=parent_required,
                session=session)
        return trial

    @proxy_method
    def fast_last_trial_id_without_inheritance(model, cls, session=None):
        """Load last trial id that did not bypass modules


        Compile SQLAlchemy core query into string for optimization

        Keyword arguments:
        session -- specify session for loading (default=relational.session)
        """
        session = session or relational.session
        if not hasattr(model, "_last_trial_id_without_inheritance"):
            ttrial = model.__table__
            _query = (
                select([ttrial.c.id]).where(ttrial.c.start.in_(
                    select([func.max(ttrial.c.start)])
                    .select_from(ttrial)
                    .where(ttrial.c.inherited_id == None)
                ))
            )
            model._last_trial_id_without_inheritance = str(_query)
        an_id = session.execute(
            model._last_trial_id_without_inheritance).fetchone()
        if not an_id:
            raise RuntimeError(
                "Not able to bypass modules check because no previous trial "
                "was found"
            )
        return an_id[0]

    @proxy_method
    def fast_update(model, cls, trial_id, finish, session=None):
        """Update finish time of trial

        Use core sqlalchemy

        Arguments:
        trial_id -- trial id
        finish -- finish time as a datetime object


        Keyword arguments:
        session -- specify session for loading (default=relational.session)
        """
        session = session or relational.session
        ttrial = model.__table__
        session.execute(
            ttrial.update()
            .values(finish=finish)
            .where(ttrial.c.id == trial_id)
        )
        session.commit()

    @proxy_method
    def fast_store(model, cls, start, script, code_hash, arguments,
                   bypass_modules, command, run, session=None):
        """Create trial and assign a new id to it

        Use core sqlalchemy

        Arguments:
        start -- trial start time
        script -- script name
        code_hash -- script hash code
        arguments -- trial arguments
        bypass_modules -- whether it captured modules or not
        command -- the full command line with noWorkflow parametes
        run -- trial created by the run command

        Keyword arguments:
        session -- specify session for loading (default=relational.session)
        """
        session = session or relational.session

        # ToDo: use core query
        parent = cls.load_parent(script, parent_required=True)
        parent_id = parent.id if parent else None

        inherited_id = None
        if bypass_modules:
            inherited_id = cls.fast_last_trial_id_without_inheritance()
        ttrial = model.__table__
        result = session.execute(
            ttrial.insert(),
            {"start": start, "script": script, "code_hash": code_hash,
             "arguments": arguments, "command": command, "run": run,
             "inherited_id": inherited_id, "parent_id": parent_id})
        tid = result.lastrowid
        session.commit()
        return tid

    @proxy_method
    def all(model, cls, session=None):
        """Return all trials

        Keyword arguments:
        session -- specify session for loading (default=relational.session)
        """
        session = session or relational.session
        return proxy_gen(session.query(model))
