# Copyright (c) 2016 Universidade Federal Fluminense (UFF)
# Copyright (c) 2016 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""Trial Model"""
from __future__ import (absolute_import, print_function,
                        division, unicode_literals)

import os

from sqlalchemy import Column, Integer, Text, TIMESTAMP
from sqlalchemy import ForeignKeyConstraint, select, func, distinct

from ...utils.formatter import PrettyLines
from ...utils.prolog import PrologDescription, PrologTrial, PrologNullableRepr
from ...utils.prolog import PrologTimestamp, PrologAttribute, PrologRepr
from ...utils.prolog import PrologNullable

from .. import relational, content, persistence_config

from .base import AlchemyProxy, proxy_class, query_many_property, proxy_gen
from .base import one, many_ref, many_viewonly_ref, backref_many, is_none
from .base import proxy

from .trial_prolog import TrialProlog
from .trial_dot import TrialDot

from .module import Module
from .dependency import Dependency
from .activation import Activation
from .head import Head
from .graphs.trial_graph import TrialGraph
from .graphs.dependency_graph import DependencyConfig, DependencyFilter
from .graphs.dependency_graph import PrologVisitor


@proxy_class                                                                     # pylint: disable=too-many-public-methods
class Trial(AlchemyProxy):
    """Represent a trial
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

    id = Column(Integer, primary_key=True)                                       # pylint: disable=invalid-name
    start = Column(TIMESTAMP)
    finish = Column(TIMESTAMP)
    script = Column(Text)
    code_hash = Column(Text)
    arguments = Column(Text)
    command = Column(Text)
    inherited_id = Column(Integer, index=True)
    parent_id = Column(Integer, index=True)
    run = Column(Integer)
    docstring = Column(Text)

    inherited = one(
        "Trial", backref="bypass_children", viewonly=True,
        remote_side=[id], primaryjoin=(id == inherited_id)
    )
    parent = one(
        "Trial", backref="children", viewonly=True,
        remote_side=[id], primaryjoin=(id == parent_id)
    )

    function_defs = many_ref("trial", "FunctionDef")
    module_dependencies = many_ref("trials", "Dependency")
    dmodules = many_ref("trials", "Module", secondary=Dependency.t)
    environment_attrs = many_ref("trial", "EnvironmentAttr")
    activations = many_ref("trial", "Activation",
                           order_by=Activation.m.start)
    file_accesses = many_viewonly_ref("trial", "FileAccess")
    objects = many_viewonly_ref("trial", "Object")
    object_values = many_viewonly_ref("trial", "ObjectValue")
    variables = many_viewonly_ref("trial", "Variable")
    variable_usages = many_viewonly_ref("trial", "VariableUsage")
    variable_dependencies = many_viewonly_ref("trial", "VariableDependency")
    tags = many_ref("trial", "Tag")

    bypass_children = backref_many("bypass_children")  # Trial.inherited
    children = backref_many("children")  # Trial.parent

    @query_many_property
    def local_modules(self):
        """Load local modules. Return SQLAlchemy query"""
        return self.modules.filter(                                              # pylint: disable=no-member
            Module.m.path.like("%{}%".format(persistence_config.base_path)))

    @query_many_property
    def modules(self):
        """Load modules. Return SQLAlchemy query"""
        if self.inherited:
            return self.inherited.modules
        return self.dmodules

    @query_many_property
    def dependencies(self):
        """Load modules. Return SQLAlchemy query"""
        if self.inherited:
            return self.inherited.dependencies
        return self.module_dependencies

    @query_many_property
    def initial_activations(self):
        """Return initial activation as a SQLAlchemy query"""
        return self.activations.filter(is_none(Activation.m.caller_id))

    DEFAULT = {
        "dependency_config.show_blackbox_dependencies": False,
        "dot.format": "png",
        "graph.width": 500,
        "graph.height": 500,
        "graph.mode": 3,
        "graph.use_cache": True,
        "prolog.use_cache": True,
    }

    REPLACE = {
        "dependency_config_show_blackbox_dependencies":
            "dependency_config.show_blackbox_dependencies",
        "dot_format": "dot.format",
        "graph_width": "graph.width",
        "graph_height": "graph.height",
        "graph_mode": "graph.mode",
        "graph_use_cache": "graph.use_cache",
        "prolog_use_cache": "prolog.use_cache",
    }

    prolog_description = PrologDescription("trial", (
        PrologTrial("id"),
        PrologTimestamp("start"),
        PrologTimestamp("finish"),
        PrologRepr("script"),
        PrologRepr("code_hash"),
        PrologRepr("command"),
        PrologNullable("inherited_id", link="trial.id"),
        PrologNullable("parent_id", link="trial.id"),
        PrologAttribute("run"),
        PrologNullableRepr("docstring"),
    ), description=(
        "informs that a given *script* with *docstring*,\n"
        "and content *code_hash*,\n"
        "executed during a time period from *start*"
        "to *finish*,\n"
        "using noWokflow's *command*,\n"
        "that generated a trial *id*.\n"
        "This trial uses modules from *inherited_id*,\n"
        "is based on *parent_id*,\n"
        "and might be a *run* or a backup trial."
    ))

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
            obj = Trial.last_trial(script=script, session=session)
            if "graph_use_cache" not in kwargs:
                kwargs["graph_use_cache"] = False
            if "prolog_use_cache" not in kwargs:
                kwargs["prolog_use_cache"] = False
        else:
            obj = Trial.load_trial(trial_ref, session=session)

        if obj is None:
            raise RuntimeError("Trial {} not found".format(trial_ref))
        super(Trial, self).__init__(obj)
        #self._store_pk(obj)
        #self._restore_instance()

        self.dependency_config = DependencyConfig()
        self.dependency_filter = DependencyFilter(self)
        self.graph = TrialGraph(self)
        self.prolog = TrialProlog(self)
        self.dot = TrialDot(self)
        self.initialize_default(kwargs)
        self._prolog_visitor = None

    @property
    def prolog_variables(self):
        """Return filtered prolog variables"""
        if not self._prolog_visitor:
            self.dependency_filter.run()
            self._prolog_visitor = PrologVisitor(self.dependency_filter)
            self._prolog_visitor.visit(self.dependency_filter.main_cluster)
        return self._prolog_visitor

    @property
    def script_content(self):
        """Return the "main" script content of the trial"""
        return PrettyLines(
            content.get(self.code_hash)
            .decode("utf-8").split("/n"))

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

    def versioned_files(self, skip_script=False, skip_local=False,
                        skip_access=False):
        """Find first files accessed in a trial
        Return map with relative path -> (code_hash, type)

        Possible types: script, module, access
        """
        files = {}
        def add(path, info):
            """Add file to dict"""
            if os.path.isabs(path):
                if not persistence_config.base_path in path:
                    return
                path = os.path.relpath(path, persistence_config.base_path)
            files[path] = info

        if not skip_script:
            add(self.script, {"code_hash": self.code_hash, "type": "script"})
        if not skip_local:
            for module in self.local_modules:                                    # pylint: disable=not-an-iterable
                add(module.path, {
                    "code_hash": module.code_hash,
                    "type": "module",
                    "name": module.name
                })
        if not skip_access:
            for faccess in reversed(list(self.file_accesses)):
                add(faccess.name, {
                    "code_hash": faccess.content_hash_before, "type": "access",
                })

        return files

    def iterate_accesses(self, path=None):
        """Iterate on all access to a path"""
        if not path or self.script.endswith(path):
            yield self.script, {"code_hash": self.code_hash, "type": "script"}
        for module in self.local_modules:                                        # pylint: disable=not-an-iterable
            if not path or module.path.endswith(path):
                yield module.path, {
                    "code_hash": module.code_hash,
                    "type": "module",
                    "name": module.name
                }
        for faccess in list(self.file_accesses):
            if not path or faccess.name.endswith(path):
                yield faccess.name, {
                    "code_hash": faccess.content_hash_before, "type": "access",
                }
                yield faccess.name, {
                    "code_hash": faccess.content_hash_after, "type": "access",
                }

    def create_head(self):
        """Create head for this trial"""
        session = relational.make_session()
        session.query(Head.m).filter(Head.m.script == self.script).delete()      # pylint: disable=no-member
        session.add(Head.m(trial_id=self.id, script=self.script))                # pylint: disable=no-member, not-callable
        session.commit()                                                         # pylint: disable=no-member

    def query(self, query):
        """Run prolog query"""
        return self.prolog.query(query)

    def _repr_html_(self):
        """Display d3 graph on ipython notebook"""
        if hasattr(self, "graph"):
            return self.graph._repr_html_()                                      # pylint: disable=protected-access
        return repr(self)

    def show(self, _print=print):
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

    @classmethod  # query
    def distinct_scripts(cls):
        """Return a set with distinct scripts"""
        return {s[0].rsplit("/", 1)[-1]
                for s in relational.session.query(distinct(cls.m.script))}

    @classmethod  # query
    def reverse_trials(cls, limit, session=None):
        """Return a generator with <limit> trials ordered by start time desc"""
        session = session or relational.session
        return proxy_gen(
            session.query(cls.m)
            .order_by(cls.m.start.desc())
            .limit(limit)
        )

    @classmethod  # query
    def last_trial(cls, script=None, parent_required=False,
                   session=None):
        """Return last trial according to start time

        Keyword arguments:
        script -- specify the desired script (default=None)
        parent_required -- valid only if script exists (default=False)
        """
        model = cls.m
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

    @classmethod  # query
    def find_by_name_and_time(cls, script, timestamp, trial=None,
                              session=None):
        """Return the first trial according to script and timestamp

        Arguments:
        script -- specify the desired script
        timestamp -- specify the start of finish time of trial

        Keyword Arguments:
        trial -- limit query to a specific trial
        """
        model = cls.m
        session = session or relational.session
        query = (
            session.query(model)
            .filter(
                (model.script == script) & (
                    model.start.like(timestamp + "%") |
                    model.finish.like(timestamp + "%")
                )
            ).order_by(model.start)
        )
        if trial:
            query = query.filter(model.id == trial)
        return proxy(query.first())


    @classmethod  # query
    def load_trial(cls, trial_ref, session=None):
        """Load trial by trial reference

        Find reference on trials id and tags name
        """
        from .tag import Tag  # avoid circular import
        session = session or relational.session
        return (
            session.query(cls.m)
            .outerjoin(Tag.m)
            .filter((cls.m.id == trial_ref) | (Tag.m.name == trial_ref))
        ).first()

    @classmethod  # query
    def load_parent(cls, script, remove=True, parent_required=False,
                    session=None):
        """Load head trial by script


        Keyword arguments:
        remove -- remove from head, after loading (default=True)
        parent_required -- valid only if script exists (default=False)
        session -- specify session for loading (default=relational.session)
        """
        session = session or relational.session
        head = Head.load_head(script, session=session)
        if head:
            trial = head.trial
            if remove:
                Head.remove(head.id, session=relational.make_session())
        elif not head:
            trial = cls.last_trial(
                script=script, parent_required=parent_required,
                session=session)
        return proxy(trial)

    @classmethod  # query
    def fast_last_trial_id(cls, session=None):
        """Load last trial id that did not bypass modules


        Compile SQLAlchemy core query into string for optimization

        Keyword arguments:
        session -- specify session for loading (default=relational.session)
        """
        session = session or relational.session
        if not hasattr(cls, "_last_trial_id"):
            ttrial = cls.t
            _query = (
                select([ttrial.c.id]).where(ttrial.c.start.in_(
                    select([func.max(ttrial.c.start)])
                    .select_from(ttrial)
                    .where(is_none(ttrial.c.inherited_id))
                ))
            )
            cls.last_trial_id = str(_query)
        an_id = session.execute(
            cls.last_trial_id).fetchone()
        if not an_id:
            raise RuntimeError(
                "Not able to bypass modules check because no previous trial "
                "was found"
            )
        return an_id[0]

    @classmethod  # query
    def fast_update(cls, trial_id, finish, docstring, session=None):
        """Update finish time of trial

        Use core sqlalchemy

        Arguments:
        trial_id -- trial id
        finish -- finish time as a datetime object


        Keyword arguments:
        session -- specify session for loading (default=relational.session)
        """
        session = session or relational.session
        ttrial = cls.t
        session.execute(
            ttrial.update()
            .values(finish=finish, docstring=docstring)
            .where(ttrial.c.id == trial_id)
        )
        session.commit()

    @classmethod  # query
    def store(cls, start, script, code_hash, arguments, bypass_modules,          # pylint: disable=too-many-arguments
              command, run, docstring, session=None):
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
            inherited_id = cls.fast_last_trial_id()
        ttrial = cls.__table__
        result = session.execute(
            ttrial.insert(),
            {"start": start, "script": script, "code_hash": code_hash,
             "arguments": arguments, "command": command, "run": run,
             "inherited_id": inherited_id, "parent_id": parent_id,
             "docstring": docstring})
        tid = result.lastrowid
        session.commit()
        return tid

    @classmethod  # query
    def all(cls, session=None):
        """Return all trials

        Keyword arguments:
        session -- specify session for loading (default=relational.session)
        """
        session = session or relational.session
        return proxy_gen(session.query(cls.m))
