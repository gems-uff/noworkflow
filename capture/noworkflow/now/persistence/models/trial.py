# Copyright (c) 2016 Universidade Federal Fluminense (UFF)
# Copyright (c) 2016 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""Trial Model"""
# pylint: disable=too-many-lines
from __future__ import (absolute_import, print_function,
                        division, unicode_literals)

import os

from sqlalchemy import Column, Integer, Text, TIMESTAMP
from sqlalchemy import ForeignKeyConstraint, select, func, distinct

from ...utils.formatter import PrettyLines
from ...utils.prolog import PrologDescription, PrologTrial
from ...utils.prolog import PrologTimestamp, PrologRepr
from ...utils.prolog import PrologNullable

from .. import relational, content, persistence_config

from .base import AlchemyProxy, proxy_class, query_many_property, proxy_gen
from .base import one, many_ref, many_viewonly_ref, backref_many, is_none
from .base import proxy

from .code_block import CodeBlock
from .activation import Activation
from .head import Head


@proxy_class
class Trial(AlchemyProxy):
    """Represent a trial

    Doctest:
    >>> from noworkflow.tests.helpers.models import TrialConfig, new_trial
    >>> id1 = new_trial(
    ...   trial=TrialConfig("finished"),
    ...   tag="1.0.0", erase=True)
    >>> id2 = new_trial(
    ...   trial=TrialConfig("finished", docstring="main script", duration=65),
    ...   tag="1.1.0")

    Initialize it by passing a trial reference (id or tag):
    >>> first_trial = Trial("1.0.0")
    >>> first_trial.id == id1
    True
    >>> trial = Trial(id2)
    >>> trial.id == id2
    True


    There are four visualization modes for the graph:
    tree: activation tree without any filters
    >>> trial.graph.mode = 0

    no match: tree transformed into a graph by the addition of sequence and
              return edges and removal of intermediate call edges
    >>> trial.graph.mode = 1

    exact match: calls are only combined when all the sub-call match
    >>> trial.graph.mode = 2

    namesapce: calls are combined without considering the sub-calls
    >>> trial.graph.mode = 3


    You can change the graph width and height by the variables:
    >>> trial.graph.width = 600
    >>> trial.graph.height = 400


    If the trial was based on another one, it is possible to access it:
    >>> trial.parent.id == id1
    True

    Similarly, it is possible to get which trials are based on the current one
    >>> list(first_trial.children)  # doctest: +ELLIPSIS
    [trial(...).]


    It is possible to check trial has finished by running:
    >>> trial.finished
    True

    It is also possible to get the trial duration in microseconds:
    >>> trial.duration
    65000000

    And as text:
    >>> trial.duration_text
    '0:01:05'

    To access the trial main script, please do:
    >>> code_block = trial.main
    >>> code_block.docstring == 'main script'
    True

    As a shortcut, you can also access the following properties.
    These properties access the main script:
    >>> str(trial.script_content)
    "'main script'\\ndef f(x):\\n    return x\\na = [1]\\nb = f(a)"
    >>> trial.docstring == 'main script'
    True
    >>> trial.code_hash == trial.main.code_hash
    True

    For a list of all code blocks, code components, evaluations, activations,
    accesses, values, compartments, dependencies and tags:
    >>> list(trial.code_blocks)  # doctest: +ELLIPSIS
    [code_block(...)., ...]
    >>> list(trial.code_components)  # doctest: +ELLIPSIS
    [code_component(...)., ...]
    >>> list(trial.evaluations)  # doctest: +ELLIPSIS
    [evaluation(...)., ...]
    >>> list(trial.activations)  # doctest: +ELLIPSIS
    [activation(...)., ...]
    >>> list(trial.file_accesses)  # doctest: +ELLIPSIS
    [access(...)., ...]
    >>> list(trial.values)  # doctest: +ELLIPSIS
    [value(...)., ...]
    >>> list(trial.compartments)  # doctest: +ELLIPSIS
    [compartment(...).]
    >>> list(trial.dependencies)  # doctest: +ELLIPSIS
    [dependency(...)., ...]
    >>> list(trial.tags)  # doctest: +ELLIPSIS
    [tag(..., '1.1.0', 'AUTO', ...).]

    To load modules, propagating inherited modules:
    >>> list(trial.modules)  # doctest: +ELLIPSIS
    [module(...)., ...]

    If you are interested only on local modules:
    >>> list(trial.local_modules)  # doctest: +ELLIPSIS
    [module(...).]
    """
    # pylint: disable=too-many-public-methods

    __tablename__ = "trial"
    __table_args__ = (
        ForeignKeyConstraint(["modules_inherited_from_trial_id"],
                             ["trial.id"], ondelete="RESTRICT"),
        ForeignKeyConstraint(["parent_id"], ["trial.id"], ondelete="SET NULL"),
        ForeignKeyConstraint(["id", "main_id"],
                             ["code_block.trial_id", "code_block.id"],
                             ondelete="SET NULL", use_alter=True),
        {"sqlite_autoincrement": True},
    )

    id = Column(  # pylint: disable=invalid-name
        Integer, primary_key=True, autoincrement=True
    )
    script = Column(Text)
    start = Column(TIMESTAMP)
    finish = Column(TIMESTAMP)
    command = Column(Text)
    path = Column(Text)
    status = Column(Text)
    modules_inherited_from_trial_id = Column(Integer, index=True)
    parent_id = Column(Integer, index=True)
    main_id = Column(Integer, index=True)


    modules_inherited_from_trial = one(
        "Trial", backref="bypass_children", viewonly=True,
        remote_side=[id], primaryjoin=(id == modules_inherited_from_trial_id)
    )
    parent = one(
        "Trial", backref="children", viewonly=True,
        remote_side=[id], primaryjoin=(id == parent_id)
    )
    main = one(
        "CodeBlock",
        remote_side=[CodeBlock.m.trial_id, CodeBlock.m.id],
        primaryjoin=((main_id == CodeBlock.m.id) &
                     (id == CodeBlock.m.trial_id)))
    code_blocks = many_viewonly_ref(
        "trial", "CodeBlock",
        uselist=True,
        remote_side=[CodeBlock.m.trial_id],
        primaryjoin=((id == CodeBlock.m.trial_id)))

    arguments = many_ref("trial", "Argument")
    environment_attrs = many_ref("trial", "EnvironmentAttr")
    _modules = many_ref("trial", "Module")

    code_components = many_viewonly_ref("trial", "CodeComponent")
    evaluations = many_viewonly_ref("trial", "Evaluation")
    activations = many_viewonly_ref(
        "trial", "Activation", order_by=Activation.m.start)
    file_accesses = many_viewonly_ref("trial", "FileAccess")
    values = many_viewonly_ref("trial", "Value")

    compartments = many_viewonly_ref("trial", "Compartment")

    dependencies = many_viewonly_ref("trial", "Dependency")
    compositions = many_viewonly_ref("trial", "Composition")

    tags = many_ref("trial", "Tag")

    # Trial.modules_inherited_from_trial
    bypass_children = backref_many("bypass_children")
    # Trial.parent
    children = backref_many("children")

    DEFAULT = {
        "dot.format": "png",
        "graph.width": 500,
        "graph.height": 500,
        "graph.mode": 3,
        "graph.use_cache": True,
        "prolog.use_cache": True,
    }

    REPLACE = {
        "dot_format": "dot.format",
        "graph_width": "graph.width",
        "graph_height": "graph.height",
        "graph_mode": "graph.mode",
        "graph_use_cache": "graph.use_cache",
        "prolog_use_cache": "prolog.use_cache",
    }

    prolog_description = PrologDescription("trial", (
        PrologTrial("id"),
        PrologRepr("script"),
        PrologTimestamp("start"),
        PrologTimestamp("finish"),
        PrologRepr("command"),
        PrologRepr("status"),
        PrologNullable("modules_inherited_from_trial_id", link="trial.id"),
        PrologNullable("parent_id", link="trial.id"),
        PrologNullable("main_id", link="code_block.id"),
    ), description=(
        "informs that a given trial (*Id*),\n"
        "executed *Script* during a time period from *Start*"
        "to *Finish*,\n"
        "using noWokflows *command*.\n"
        "This trial might by backup/finished/unfinished (*Status*).\n"
        "This trial uses modules from *ModulesInheritedFromTrialId*,\n"
        "is based on *ParentId*,\n"
        "and represents the script *CodeBlockId*."
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

        from ...models.dependency_graph.config import DependencyConfig
        from ...models.graphs.trial_graph import TrialGraph
        from ...models.trial_prolog import TrialProlog
        from ...models.trial_dot import TrialDot

        self.dependency_config = DependencyConfig()
        self._dependency_clusterizer = None
        self._clusterizer_mode = None
        self.graph = TrialGraph(self)

        self.prolog = TrialProlog(self)
        self.dot = TrialDot(self)
        self.initialize_default(kwargs)
        self._prolog_visitor = None

    @property
    def dependency_clusterizer(self):
        """Return clusterizer"""
        config = self.dependency_config
        if config.mode != self._clusterizer_mode:
            self._clusterizer_mode = config.mode
            self._dependency_clusterizer = config.clusterizer(self)
        return self._dependency_clusterizer

    @query_many_property
    def modules(self):
        """Load modules. Return SQLAlchemy query


        Doctest:
        >>> from noworkflow.tests.helpers.models import TrialConfig, new_trial
        >>> trial1 = Trial(new_trial(TrialConfig("unfinished"), erase=True))
        >>> trial2 = Trial(new_trial(TrialConfig(
        ...     "unfinished", bypass_modules=True)))

        Return this modules, if it did not bypass modules:
        >>> _ids1 = sorted([m.id for m in trial1._modules])
        >>> ids1 = sorted([m.id for m in trial1.modules])
        >>> _ids1 == ids1
        True

        Do not return this modules, if it bypassed modules:
        >>> _ids2 = sorted([m.id for m in trial2._modules])
        >>> ids2 = sorted([m.id for m in trial2.modules])
        >>> _ids2 != ids2
        True

        Instead, return the inherited trial modules:
        >>> _ids1 == ids2
        True
        """
        if self.modules_inherited_from_trial:
            return self.modules_inherited_from_trial.modules
        return self._modules


    @property
    def initial_activation(self):
        """Return initial activation


        Doctest:
        >>> from noworkflow.tests.helpers.models import new_trial, TrialConfig
        >>> from noworkflow.tests.helpers.models import FuncConfig
        >>> from noworkflow.tests.helpers.models import AssignConfig
        >>> from noworkflow.now.persistence.models import Trial
        >>> assign = AssignConfig()
        >>> function = FuncConfig("f", 1, 0, 2, 8)
        >>> trial_config = TrialConfig("finished")
        >>> trial_id = new_trial(trial_config, assignment=assign,
        ...                      function=function, erase=True)
        >>> activation = Activation((trial_id, assign.f_activation))
        >>> trial = Trial(trial_id)
        >>> main_activation = trial.main.this_component.first_evaluation

        Return initial activation:
        >>> trial.initial_activation.id == trial_config.main_act
        True
        """
        if self.main.this_component.first_evaluation is None:
            return None
        return self.main.this_component.first_evaluation.this_activation

    @property
    def local_modules(self):
        """Load local modules

        Doctest:
        >>> from noworkflow.tests.helpers.models import TrialConfig, new_trial
        >>> from noworkflow.tests.helpers.models import modules
        >>> trial_id = new_trial(TrialConfig(path="/home/now"), erase=True)
        >>> trial = Trial(trial_id)

        Return empty list if there are no modules:
        >>> list(trial.local_modules)
        []

        Do not return modules outside the trial path:
        >>> m1 = modules.add(
        ...     trial_id, "external", "1.0.1", "/home/external.py", None, 0)
        >>> modules.do_store()
        >>> list(trial.local_modules)
        []

        Return modules inside the trial path:
        >>> m2 = modules.add(
        ...    trial_id, "inte", "1.0.1", "/home/now/inte.py", None, 0)
        >>> modules.do_store()
        >>> list(trial.local_modules)  # doctest: +ELLIPSIS
        [module(..., 'inte', '1.0.1').]

        Return modules with relative path:
        >>> m3 = modules.add(
        ...    trial_id, "inte2", "1.0.2", "inte2.py", None, 0)
        >>> modules.do_store()
        >>> list(trial.local_modules)  # doctest: +ELLIPSIS
        [module(..., 'inte', '1.0.1')., module(..., 'inte2', '1.0.2').]
        """
        # pylint: disable=not-an-iterable
        for module in self.modules:
            path = module.path
            if path is None:
                continue
            elif not os.path.isabs(path):
                yield module
            elif path.startswith(self.path):
                yield module

    @property
    def script_content(self):
        """Return the "main" script content of the trial


        Doctest:
        >>> from noworkflow.tests.helpers.models import TrialConfig, new_trial
        >>> trial = Trial(new_trial(TrialConfig(docstring="block"),erase=True))

        Return script_content:
        >>> str(trial.script_content) #doctest: +ELLIPSIS
        "'block'\\ndef f(x):\\n    return x\\na = [1]\\nb = f(a)"
        """
        return self.main.content

    @property
    def docstring(self):
        """Return trial docstring


        Doctest:
        >>> from noworkflow.tests.helpers.models import new_trial
        >>> trial = Trial(new_trial(erase=True))

        Return docstring:
        >>> trial.docstring == 'block'
        True
        """
        return self.main.docstring

    @property
    def code_hash(self):
        """Return trial code hash


        Doctest:
        >>> from noworkflow.tests.helpers.models import new_trial
        >>> trial = Trial(new_trial(erase=True))

        Return code hash:
        >>> len(trial.code_hash)
        40
        """
        return self.main.code_hash

    @property
    def finished(self):
        """Check if trial has finished

        Doctest:
        >>> from noworkflow.tests.helpers.models import TrialConfig, new_trial
        >>> id1 = new_trial(TrialConfig("finished"), erase=True)
        >>> id2 = new_trial(TrialConfig("unfinished"))

        Trial has finished:
        >>> Trial(id1).finished
        True

        Trial has not finished:
        >>> Trial(id2).finished
        False
        """
        return self.status == "finished"

    @property
    def backup(self):
        """Check if trial has finished

        Doctest:
        >>> from noworkflow.tests.helpers.models import TrialConfig, new_trial
        >>> id1 = new_trial(TrialConfig("backup"), erase=True)
        >>> id2 = new_trial(TrialConfig("unfinished"))

        Trial is backup:
        >>> Trial(id1).backup
        True

        Trial has not finished:
        >>> Trial(id2).backup
        False
        """
        return self.status == "backup"

    @property
    def status_letter(self):
        """Return letter representing status

        Doctest:
        >>> from noworkflow.tests.helpers.models import TrialConfig, new_trial
        >>> id1 = new_trial(TrialConfig("backup"), erase=True)
        >>> id2 = new_trial(TrialConfig("unfinished"))
        >>> id3 = new_trial(TrialConfig("finished"))


        Trial is backup:
        >>> print(Trial(id1).status_letter)
        b

        Trial has not finished:
        >>> print(Trial(id2).status_letter)
        f

        Trial has finished:
        >>> print(Trial(id3).status_letter)
        *
        """
        if self.status == "backup":
            return "b"
        elif self.status == "finished":
            return "*"
        return "f"

    @property
    def duration(self):
        """Calculate trial duration. Return microseconds


        Doctest:
        >>> from noworkflow.tests.helpers.models import TrialConfig, new_trial
        >>> trial = Trial(new_trial(TrialConfig(duration=65), erase=True))

        Return duration:
        >>> trial.duration
        65000000
        """
        if self.finish:
            return int((self.finish - self.start).total_seconds() * 1000000)
        return 0

    @property
    def duration_text(self):
        """Calculate trial duration. Return formatted str


        Doctest:
        >>> from noworkflow.tests.helpers.models import TrialConfig, new_trial
        >>> trial = Trial(new_trial(TrialConfig(duration=65), erase=True))

        Return duration:
        >>> trial.duration_text
        '0:01:05'
        """
        if self.finish:
            return str(self.finish - self.start)
        return "None"

    @property
    def environment(self):
        """Return dict: environment variables -> value


        Doctest:
        >>> from noworkflow.tests.helpers.models import TrialConfig, new_trial
        >>> trial = Trial(new_trial(TrialConfig(
        ...     "unfinished", path="/home/now"), user="now", erase=True))

        Return environment dict
        >>> print(repr(sorted(trial.environment.items())
        ... ).replace("u'", "'"))
        [('CWD', '/home/now'), ('USER', 'now')]
        """
        return {e.name: e.value for e in self.environment_attrs}

    @property
    def argument_dict(self):
        """Return dict: argument -> value


        Doctest:
        >>> from noworkflow.tests.helpers.models import TrialConfig, new_trial
        >>> trial = Trial(new_trial(TrialConfig(
        ...     "unfinished", script="main.py", bypass_modules=False
        ... ), erase=True))

        Return argument dict
        >>> print(repr(sorted(trial.argument_dict.items())
        ... ).replace("u'", "'"))
        [('bypass_modules', 'False'), ('script', 'main.py')]
        """
        return {a.name: a.value for a in self.arguments}

    def versioned_files(self, script=True, local=True, access=True):
        """Find first files accessed in a trial
        Return map with relative path -> (code_hash, type)

        Possible types: script, module, access


        Doctest:
        >>> from noworkflow.tests.helpers.models import TrialConfig, new_trial
        >>> from noworkflow.tests.helpers.models import AccessConfig
        >>> trial = Trial(new_trial(
        ...     TrialConfig("finished", script="main.py"),
        ...     AccessConfig(
        ...         read_file="file.txt", write_file="file2.txt",
        ...         read_hash="abc", write_hash_before=None,
        ...         write_hash_after="def"
        ...     ), erase=True))

        Get only script:
        >>> print(repr([(path, sorted(dic.items()))
        ...  for path, dic in sorted(
        ...     trial.versioned_files(local=False, access=False).items()
        ...  )
        ... ]).replace("u'", "'")) #doctest: +ELLIPSIS +NORMALIZE_WHITESPACE
        [('main.py', [('code_hash', '...'), ('type', 'script')])]

        Get only modules:
        >>> print(repr([(path, sorted(dic.items()))
        ...  for path, dic in sorted(
        ...     trial.versioned_files(script=False, access=False).items()
        ...  )
        ... ]).replace("u'", "'")) #doctest: +ELLIPSIS +NORMALIZE_WHITESPACE
        [('internal.py', [('code_hash', '...'), ('name', 'internal'),
                          ('type', 'module')])]

        Get only accesses:
        >>> print(repr([(path, sorted(dic.items()))
        ...  for path, dic in sorted(
        ...     trial.versioned_files(script=False, local=False).items()
        ...  )
        ... ]).replace("u'", "'")) #doctest: +ELLIPSIS +NORMALIZE_WHITESPACE
        [('file.txt', [('code_hash', 'abc'), ('type', 'access')]),
         ('file2.txt', [('code_hash', None), ('type', 'access')])]

        Get everythin:
        >>> print(repr([(path, sorted(dic.items()))
        ...  for path, dic in sorted(
        ...     trial.versioned_files().items()
        ...  )
        ... ]).replace("u'", "'")) #doctest: +ELLIPSIS +NORMALIZE_WHITESPACE
        [('file.txt', [('code_hash', 'abc'), ('type', 'access')]),
         ('file2.txt', [('code_hash', None), ('type', 'access')]),
         ('internal.py', [('code_hash', '...'), ('name', 'internal'),
                          ('type', 'module')]),
         ('main.py', [('code_hash', '...'), ('type', 'script')])]
        """
        files = {}
        def add(path, info):
            """Add file to dict"""
            if os.path.isabs(path):
                if not path.startswith(self.path):
                    return
                path = os.path.relpath(path, persistence_config.base_path)
            files[path] = info

        if script:
            add(self.script, {"code_hash": self.code_hash, "type": "script"})
        if local:
            # pylint: disable=not-an-iterable
            for module in self.local_modules:
                code_hash = module.code_hash
                if code_hash:
                    add(module.path, {
                        "code_hash": code_hash,
                        "type": "module",
                        "name": module.name
                    })
        if access:
            for faccess in reversed(list(self.file_accesses)):
                add(faccess.name, {
                    "code_hash": faccess.content_hash_before, "type": "access",
                })

        return files

    def iterate_accesses(self, path=None):
        """Iterate on all access to a path


        Doctest:
        >>> from noworkflow.tests.helpers.models import TrialConfig, new_trial
        >>> from noworkflow.tests.helpers.models import AccessConfig
        >>> trial = Trial(new_trial(TrialConfig(
        ...     "finished", script="main.py"
        ... ), AccessConfig(
        ...    read_file="file.txt", write_file="file2.txt",
        ...    read_hash="abc", write_hash_before=None,
        ...    write_hash_after="def"
        ... ), erase=True))

        Generate all trial accesses:
        >>> print(repr([(name, sorted(dic.items()))
        ...  for name, dic in trial.iterate_accesses()
        ... ]).replace("u'", "'")) #doctest: +ELLIPSIS +NORMALIZE_WHITESPACE
        [('main.py', [('code_hash', '...'), ('type', 'script')]),
         ('internal.py', [('code_hash', '...'), ('name', 'internal'),
                          ('type', 'module')]),
         ('file.txt', [('code_hash', 'abc'), ('type', 'access')]),
         ('file.txt', [('code_hash', 'abc'), ('type', 'access')]),
         ('file2.txt', [('code_hash', None), ('type', 'access')]),
         ('file2.txt', [('code_hash', 'def'), ('type', 'access')])]

        Filter by path:
        >>> print(repr([(name, sorted(dic.items()))
        ...  for name, dic in trial.iterate_accesses("file2.txt")
        ... ]).replace("u'", "'")) #doctest: +ELLIPSIS +NORMALIZE_WHITESPACE
        [('file2.txt', [('code_hash', None), ('type', 'access')]),
         ('file2.txt', [('code_hash', 'def'), ('type', 'access')])]
        """
        if not path or self.script.endswith(path):
            yield self.script, {"code_hash": self.code_hash, "type": "script"}
        # pylint: disable=not-an-iterable
        for module in self.local_modules:
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
        """Create head for this trial


        Doctest:
        >>> from noworkflow.tests.helpers.models import TrialConfig, new_trial
        >>> from noworkflow.tests.helpers.models import count
        >>> id1 = new_trial(TrialConfig(script="main.py"), erase=True)
        >>> id2 = new_trial(TrialConfig(script="main.py"))
        >>> id3 = new_trial(TrialConfig(script="main2.py"))

        Create a new head row:
        >>> count(Head)
        0
        >>> trial = Trial(id1)
        >>> trial.create_head()
        >>> count(Head)
        1

        Remove old head if there is a head for the same script:
        >>> trial = Trial(id2)
        >>> trial.create_head()
        >>> count(Head)
        1

        Create new head for different script:
        >>> trial = Trial(id3)
        >>> trial.create_head()
        >>> count(Head)
        2

        """
        # pylint: disable=no-member, not-callable
        session = relational.make_session()
        session.query(Head.m).filter(Head.m.script == self.script).delete()
        session.add(Head.m(trial_id=self.id, script=self.script))
        session.commit()

    def show(self, print_=print):
        """Print trial information


        Doctest:
        >>> from noworkflow.tests.helpers.models import TrialConfig, new_trial
        >>> from textwrap import dedent
        >>> id_ = new_trial(TrialConfig(
        ...     year=2016, month=4, day=8, hour=18, minute=17, second=0,
        ...     duration=65, script="main.py"
        ... ), erase=True)


        Show trial:
        >>> Trial(id_).show(
        ...     print_=lambda x: print(dedent(x)))  #doctest: +ELLIPSIS
        Id: ...
        Inherited Id: None
        Script: main.py
        Code hash: ...
        Start: 2016-04-08 18:17:00
        Finish: 2016-04-08 18:18:05
        Duration: 0:01:05
        """
        print_("""\
            Id: {t.id}
            Status: {status}
            Inherited Id: {t.modules_inherited_from_trial_id}
            Script: {t.script}
            Code hash: {t.code_hash}
            Start: {t.start}
            Finish: {t.finish}
            Duration: {t.duration_text}""".format(
                t=self, status=self.status.capitalize()
            ))

    def _repr_html_(self):
        """Display d3 graph on ipython notebook"""
        if hasattr(self, "graph"):
            # pylint: disable=protected-access
            return self.graph._repr_html_()
        return repr(self)

    @classmethod  # query
    def distinct_scripts(cls):
        """Return a set with distinct scripts

        Doctest:
        >>> from noworkflow.tests.helpers.models import TrialConfig, new_trial
        >>> id1 = new_trial(TrialConfig(script="main.py"), erase=True)
        >>> id2 = new_trial(TrialConfig(script="main2.py"))
        >>> id3 = new_trial(TrialConfig(script="main3.py"))
        >>> id4 = new_trial(TrialConfig(script="main.py"))

        Return all scripts:
        >>> print(repr(sorted(list(Trial.distinct_scripts()))
        ... ).replace("u'", "'"))
        ['main.py', 'main2.py', 'main3.py']
        """
        return {s[0].rsplit("/", 1)[-1]
                for s in relational.session.query(distinct(cls.m.script))}

    @classmethod  # query
    def last_trial(cls, script=None, check=False, session=None):
        """Return last trial according to start time


        Keyword arguments:
        script -- specify the desired script (default=None)
        check -- valid only if script exists (default=False)


        Doctest:
        >>> from noworkflow.tests.helpers.models import TrialConfig, new_trial
        >>> TrialConfig.erase()

        Return None if there is no trial:
        >>> Trial.last_trial()

        Return trial if trial exists:
        >>> id1 = new_trial(TrialConfig(minute=47, script="main.py"))
        >>> trial = Trial.last_trial()
        >>> trial.id == id1
        True

        Return last trial:
        >>> id2 = new_trial(TrialConfig(minute=49, script="main2.py"))
        >>> trial = Trial.last_trial()
        >>> trial.id == id2
        True

        Return last trial refering to script:
        >>> trial = Trial.last_trial(script="main.py")
        >>> trial.id == id1
        True

        Return last trial if script does not exist:
        >>> trial = Trial.last_trial(script="main3.py")
        >>> trial.id == id2
        True

        Return None if script does not exist and check=True:
        >>> Trial.last_trial(script="main3.py", check=True)
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
        if trial or check:
            return trial
        return (
            session.query(model)
            .filter(model.start.in_(
                select([func.max(model.start)])
            ))
        ).first()

    @classmethod  # query
    def find_by_name_and_time(cls, script, time, trial=None, session=None):
        """Return the first trial according to script and timestamp


        Arguments:
        script -- specify the desired script
        time -- specify the start of finish time of trial

        Keyword Arguments:
        trial -- limit query to a specific trial


        Doctest:
        >>> from noworkflow.tests.helpers.models import TrialConfig, new_trial
        >>> id1 = new_trial(TrialConfig(year=2016, month=4, script="main.py"),
        ...     erase=True)
        >>> id2 = new_trial(TrialConfig(year=2016, month=5, script="main.py"))
        >>> id3 = new_trial(TrialConfig(year=2016, month=4, script="main2.py"))

        Return trial if name and time matches:
        >>> trial = Trial.find_by_name_and_time("main.py", "2016")
        >>> trial.id == id1
        True
        >>> trial = Trial.find_by_name_and_time("main.py", "2016-05")
        >>> trial.id == id2
        True
        >>> trial = Trial.find_by_name_and_time("main2.py", "2016")
        >>> trial.id == id3
        True

        Return None if there is no match:
        >>> Trial.find_by_name_and_time("main2.py", "2016-05")
        >>> Trial.find_by_name_and_time("main3.py", "2016")

        Return trial if trial filter is right:
        >>> trial = Trial.find_by_name_and_time("main2.py", "2016", trial=id3)
        >>> trial.id == id3
        True

        Return None if trial filter does not match:
        >>> Trial.find_by_name_and_time("main.py", "2016", trial=id3)
        """
        model = cls.m
        session = session or relational.session
        query = (
            session.query(model)
            .filter(
                (model.script == script) & (
                    model.start.like(time + "%") |
                    model.finish.like(time + "%")
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


        Doctest:
        >>> from noworkflow.tests.helpers.models import TrialConfig, new_trial
        >>> from noworkflow.tests.helpers.models import tag_params
        >>> from noworkflow.now.persistence.models import Tag

        Return trial if id matches:
        >>> id1 = new_trial(erase=True)
        >>> trial = Trial.load_trial(id1)
        >>> trial.id == id1
        True

        Return None if there is no match:
        >>> Trial.load_trial("invalid_id")

        Return trial if tag matches:
        >>> session = relational.make_session()
        >>> _ = Tag.create(session=session, **tag_params(id1, name="tag"))
        >>> trial = Trial.load_trial("tag")
        >>> trial.id == id1
        True
        """
        from .tag import Tag  # avoid circular import
        session = session or relational.session
        return (
            session.query(cls.m)
            .outerjoin(Tag.m)
            .filter((cls.m.id == trial_ref) | (Tag.m.name == trial_ref))
        ).first()

    @classmethod  # query
    def load_parent(cls, script, remove=True, check=False, session=None):
        """Load head trial by script


        Keyword arguments:
        remove -- remove from head, after loading (default=True)
        check -- parent valid only if script exists (default=False)
        session -- specify session for loading (default=relational.session)


        Doctest:
        >>> from noworkflow.tests.helpers.models import TrialConfig, new_trial
        >>> from noworkflow.tests.helpers.models import count

        Return last_trial object if there is not head:
        >>> id1 = new_trial(TrialConfig(minute=0, script="main.py"),erase=True)
        >>> trial = Trial.load_parent("main.py")
        >>> trial.id == id1
        True

        Return trial if script is not found, by parent is not required
        >>> trial = Trial.load_parent("other.py")
        >>> trial.id == id1
        True

        Returnsnone if script is not found, and check is True
        >>> trial = Trial.load_parent("other.py", check=True)
        >>> trial

        Return Head trial if head exists. Don't remove head if remove=False
        >>> id2 = new_trial(TrialConfig(minute=1, script="main.py"))
        >>> session = relational.make_session()
        >>> session.add(Head.m(trial_id=id1, script="main.py"))
        >>> session.commit()
        >>> count(Head)
        1
        >>> trial = Trial.load_parent("main.py", remove=False)
        >>> trial.id == id1
        True
        >>> count(Head)
        1

        Returns Head trial if head exists. Remove head if remove=true (default)
        >>> trial = Trial.load_parent("main.py")
        >>> trial.id == id1
        True
        >>> count(Head)
        0
        """
        session = session or relational.session
        head = Head.load_head(script, session=session)
        if head:
            trial = head.trial
            if remove:
                Head.remove(head.id, session=relational.make_session())
        elif not head:
            trial = cls.last_trial(
                script=script, check=check,
                session=session)
        return proxy(trial)

    @classmethod  # query
    def fast_last_trial_id(cls, session=None):
        """Load last trial id that did not bypass modules
        Compile SQLAlchemy core query into string for optimization


        Keyword arguments:
        session -- specify session for loading (default=relational.session)


        Doctest:
        >>> from noworkflow.tests.helpers.models import TrialConfig, new_trial
        >>> TrialConfig.erase()

        Raise RuntimerError if there is no trial:
        >>> Trial.fast_last_trial_id()
        Traceback (most recent call last):
          ...
        RuntimeError: Not able to bypass modules check.
            No previous trial was found

        Return the last existing trial id:
        >>> id1 = new_trial()
        >>> Trial.fast_last_trial_id() == id1
        True

        Only if the trial did not bypass modules:
        >>> id2 = new_trial(TrialConfig(minute=38, bypass_modules=True))
        >>> Trial.fast_last_trial_id() == id1
        True
        """
        session = session or relational.session
        if not hasattr(cls, "_last_trial_id"):
            ttrial = cls.t
            _query = (
                select([ttrial.c.id]).where(ttrial.c.start.in_(
                    select([func.max(ttrial.c.start)])
                    .select_from(ttrial)
                    .where(is_none(ttrial.c.modules_inherited_from_trial_id))
                ))
            )
            cls.last_trial_id = str(_query)
        an_id = session.execute(
            cls.last_trial_id).fetchone()
        if not an_id:
            raise RuntimeError(
                "Not able to bypass modules check.\n    "
                "No previous trial was found"
            )
        return an_id[0]

    @classmethod  # query
    def fast_update(cls, trial_id, main_id, finish, status, session=None):
        """Update finish time, main_id, and status of trial

        Use core sqlalchemy

        Arguments:
        trial_id -- trial id
        main_id -- id of main code_block
        finish -- finish time
        status -- trial status (finished/unfinished)


        Keyword arguments:
        session -- specify session for loading (default=relational.session)

        Doctest:
        >>> from noworkflow.tests.helpers.models import erase_db, select_trial
        >>> from noworkflow.tests.helpers.models import trial_params
        >>> from noworkflow.tests.helpers.models import trial_update_params
        >>> erase_db()

        Set main_id, finish and status of an existing trial:
        >>> trial_id = Trial.create(**trial_params(minute=39))
        >>> par = trial_update_params()
        >>> main_id, finish = par["main_id"], par["finish"]
        >>> status = par["status"]
        >>> Trial.fast_update(trial_id, main_id, finish, status)
        >>> trial = select_trial(trial_id)
        >>> trial.finish == finish
        True
        >>> trial.status == status
        True
        >>> trial.main_id == main_id
        True
        """
        # pylint: disable=too-many-arguments
        session = session or relational.session
        ttrial = cls.t
        session.execute(
            ttrial.update()
            .values(finish=finish, status=status, main_id=main_id)
            .where(ttrial.c.id == trial_id)
        )
        session.commit()

    @classmethod  # query
    def create(cls, script, start, command, path, bypass_modules, session=None):
        """Create trial and assign a new id to it
        Use core sqlalchemy


        Arguments:
        script -- script name
        start -- trial start time
        path -- trial base directory
        command -- the full command line with noWorkflow parametes
        bypass_modules -- whether it captured modules or not

        Keyword arguments:
        session -- specify session for loading (default=relational.session)


        Doctest:
        >>> from noworkflow.tests.helpers.models import erase_db, select_trial
        >>> from noworkflow.tests.helpers.models import trial_params
        >>> erase_db()

        Create a trial with script, start, path, command and bypass_modules.
        The first trial has no parent_id and does not inherit modules:
        >>> par = trial_params()
        >>> script, start, path = par["script"], par["start"], par["path"]
        >>> command, bypass_modules = par["command"], par["bypass_modules"]
        >>> id1 = Trial.create(script, start, command, path, bypass_modules)
        >>> trial = select_trial(id1)
        >>> trial.id == id1
        True
        >>> trial.script == script
        True
        >>> trial.start == start
        True
        >>> trial.finish
        >>> trial.command == command
        True
        >>> trial.path == path
        True
        >>> trial.status == 'ongoing'
        True
        >>> trial.modules_inherited_from_trial_id
        >>> trial.parent_id
        >>> trial.main_id

        Set parent id if there is a trial:
        >>> id2 = Trial.create(**trial_params(minute=25))
        >>> trial = select_trial(id2)
        >>> trial.parent_id == id1
        True
        >>> trial.modules_inherited_from_trial_id

        Set inherited trial if bypass_modules=True
        >>> id3 = Trial.create(**trial_params(minute=32, bypass_modules=True))
        >>> trial = select_trial(id3)
        >>> trial.modules_inherited_from_trial_id == id2
        True

        Set inherited trial to a trial that did not inherit
        modules. Note that it sets `modules_inherited_from_trial_id` to `id2`
        >>> id4 = Trial.create(**trial_params(minute=33, bypass_modules=True))
        >>> trial = select_trial(id4)
        >>> trial.modules_inherited_from_trial_id == id2
        True
        """
        # pylint: disable=too-many-arguments
        session = session or relational.session

        # ToDo: use core query
        parent = cls.load_parent(script, check=True)
        parent_id = parent.id if parent else None

        inherited_id = None
        if bypass_modules:
            inherited_id = cls.fast_last_trial_id()
        ttrial = cls.t
        result = session.execute(
            ttrial.insert(),
            {"script": script, "start": start, "command": command,
             "path": path,
             "status": "ongoing", "parent_id": parent_id,
             "modules_inherited_from_trial_id": inherited_id})
        tid = result.lastrowid
        session.commit()
        return tid

    @classmethod  # query
    def reverse_trials(cls, limit, session=None):
        """Return a generator with <limit> trials ordered by start time desc


        Doctest:
        >>> from noworkflow.tests.helpers.models import TrialConfig, new_trial
        >>> id1 = new_trial(TrialConfig(minute=4), erase=True)
        >>> id2 = new_trial(TrialConfig(minute=20))

        Return trials in reverse order:
        >>> [t.id for t in Trial.reverse_trials(2)] == [id2, id1]
        True

        Limit number of trials:
        >>> [t.id for t in Trial.reverse_trials(1)] == [id2]
        True
        """
        session = session or relational.session
        return proxy_gen(
            session.query(cls.m)
            .order_by(cls.m.start.desc())
            .limit(limit)
        )
