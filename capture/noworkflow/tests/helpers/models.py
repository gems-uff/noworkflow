# Copyright (c) 2015 Universidade Federal Fluminense (UFF)
# Copyright (c) 2015 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""Models helpers"""
from __future__ import (absolute_import, print_function,
                        division, unicode_literals)

from datetime import datetime, timedelta
from textwrap import dedent
from sqlalchemy import select, func

from collections import namedtuple


from ...now.persistence.lightweight import ObjectStore, SharedObjectStore
from ...now.persistence.lightweight import CodeBlockLW, CodeComponentLW
from ...now.persistence.lightweight import ActivationLW, EvaluationLW
from ...now.persistence.lightweight import DependencyLW, FileAccessLW
from ...now.persistence.lightweight import CellTagsLW

from ...now.persistence.lightweight import ModuleLW
from ...now.persistence.lightweight import MemberLW
from ...now.persistence.lightweight import EnvironmentAttrLW, ArgumentLW

from ...now.persistence.models.trial import Trial
from ...now.persistence.models.head import Head
from ...now.persistence.models.tag import Tag
from ...now.persistence.models.graph_cache import GraphCache
from ...now.persistence import relational
from ...now.collection.metadata import Metascript


trial_list = {}
meta = None
m1, m2 = 1, 2

def restart_object_store(trial_id=None):
    """Restart all object store"""
    global components, blocks, evaluations, activations, dependencies
    global file_accesses, modules, members
    global environment_attrs, arguments
    global meta

    if not trial_id:
        meta = Metascript()
    else:
        meta = trial_list[trial_id]

    components = meta.code_components_store
    blocks = meta.code_blocks_store
    evaluations = meta.evaluations_store
    activations = meta.activations_store
    dependencies = meta.dependencies_store
    file_accesses = meta.file_accesses_store
    members = meta.members_store
    modules = meta.modules_store
    environment_attrs = meta.environment_attrs_store
    arguments = meta.arguments_store

restart_object_store()


def erase_database():
    """Remove all rows from database"""
    relational.session.execute(GraphCache.t.delete())
    relational.session.execute(Trial.t.delete())
    relational.session.execute(Head.t.delete())
    relational.session.execute(Tag.t.delete())
    relational.session.execute(CodeComponentLW.model.t.delete())
    relational.session.execute(CodeBlockLW.model.t.delete())
    relational.session.execute(EvaluationLW.model.t.delete())
    relational.session.execute(ActivationLW.model.t.delete())
    relational.session.execute(DependencyLW.model.t.delete())
    relational.session.execute(FileAccessLW.model.t.delete())
    relational.session.execute(CellTagsLW.model.t.delete())
    relational.session.execute(MemberLW.model.t.delete())
    relational.session.execute(ModuleLW.model.t.delete())
    relational.session.execute(EnvironmentAttrLW.model.t.delete())
    relational.session.execute(ArgumentLW.model.t.delete())
    relational.session.expire_all()
    restart_object_store()

erase_db = erase_database

def trial_params(year=2016, month=4, day=8, hour=1, minute=18, second=0,
                 bypass_modules=False, script="main.py", path="/home/now"):
    """Return default trial params"""
    return {
        "script": script,
        "start":  datetime(year=year, month=month, day=day,
                           hour=hour, minute=minute, second=second),
        "command": "test",
        "path": path,
        "bypass_modules": bypass_modules,
    }


def trial_update_params(minute=56, main_id=1, status="finished"):
    """Return default trial update params"""
    return {
        "main_id": main_id,
        "finish": datetime(year=2016, month=4, day=8, hour=1, minute=minute),
        "status": status,
    }


def select_trial(id_):
    """Select trial by id"""
    return relational.session.get(Trial.m, id_)


def count(model):
    """Count tuples from model"""
    return relational.session.query(func.count(model.m.id)).scalar()


def tag_params(trial_id, name="tag", type_="AUTO", minute=20):
    """Return default tag params"""
    return {
        "trial_id": trial_id,
        "name": name,
        "type_": type_,
        "timestamp": datetime(year=2016, month=4, day=8, hour=1, minute=minute)
    }


def graph_cache_params(type_="tree", name="cache1", dur=0,
                       attr="", hash_="abcd"):
    """Return default graph_cache params"""
    return {
        "type_": type_,
        "name": name,
        "dur": dur,
        "attr": attr,
        "hash_": hash_,
    }


def component_params(trial_id, name="main.py", type_="script", mode="w",
                     first_char_line=1, first_char_column=0,
                     last_char_line=1, last_char_column=7,
                     container_id=None, ):
    """Return default component params"""
    return [trial_id, name, type_, mode, first_char_line, first_char_column,
            last_char_line, last_char_column, container_id]


def block_params(id_, trial_id, code="'block'", docstring="block", name="codeblock"):
    """Return default code block params"""
    return [id_, trial_id, code, False, docstring, name]


def evaluation_params(trial_id, code_component_id, activation_id, repr_=None, checkpoint=65):
    """Return evaluation params"""
    return [trial_id, code_component_id, activation_id, checkpoint, repr_]


def activation_params(evaluation, trial_id, code_block_id, name="main.py", start=65):
    """Return activation params"""
    return [evaluation, trial_id, name, start, code_block_id]


def access_params(trial_id, name="file.txt", checkpoint=0):
    return [trial_id, name, checkpoint]


class ConfigObj(object):

    def __init__(self):
        self.meta = None
        self.start = 65

    def comp(self, name, type_, mode, container_id, **kwargs):
        meta = self.meta
        return meta.code_components_store.add(*component_params(
            meta.trial_id,
            name=name, type_=type_, mode=mode, container_id=container_id,
            **kwargs
        ))

    def evaluation(self, code_component_id, activation_id, repr_, delta):
        meta = self.meta
        checkpoint = self.start + delta
        return meta.evaluations_store.add(*evaluation_params(
            meta.trial_id,
            code_component_id, activation_id, repr_=repr_, checkpoint=checkpoint
        ))

    def member(self, collection_activation_id, collection_id,
               member_activation_id, member_id, delta,
               key="[0]", type_="Put"):
        meta = self.meta
        checkpoint = self.start + delta
        return meta.members_store.add(
            meta.trial_id, collection_activation_id, collection_id,
            member_activation_id, member_id, key, checkpoint, type_
        )


class FuncConfig(ConfigObj):

    def __init__(self, name="f", first_line=1, first_column=0,
                 last_line=2, last_column=12, param="x",
                 global_name="", docstring=None):
        super(FuncConfig, self).__init__()
        self.name = name
        self.first_char_line = first_line
        self.first_char_column = first_column
        self.last_char_line = last_line
        self.last_char_column = last_column
        self.param = param
        self.global_name = global_name
        self.code = "def {0}({1}):\n".format(name, param)
        self.docstring = docstring
        if docstring is not None:
            self.code += "    '{}'\n".format(docstring)
        if global_name:
            self.code += "    global {}\n".format(global_name)
        self.code += "    return {}".format(param)

        self.id = -1  # pylint: disable=invalid-name
        self.param_variable = None
        self.param_return = None
        self.return_ = None
        self.f_eval = None
        self.function_repr = None
        self.global_var = None
        self.start = 0
        self.x_param_eval = None
        self.x_return_eval = None
        self.return_eval = None
        self.global_eval = None

    def insert(self, meta, container_id):
        self.meta = meta
        self.id = self.comp(
            self.name, "function_def", "w", container_id,
            first_char_line=self.first_char_line,
            first_char_column=self.first_char_column,
            last_char_line=self.last_char_line,
            last_char_column=self.last_char_column,
        )
        meta.code_blocks_store.add(*block_params(
            self.id, self.meta.trial_id,
            code=self.code, docstring=self.docstring
        ))
        return self.id

    def insert_subcomponents(self):
        self.param_variable = self.comp(self.param, "param", "w", self.id)
        self.param_return = self.comp(self.param, "variable", "r", self.id)
        self.return_ = self.comp("return", "return", "r", self.id)
        if self.global_name:
            self.global_var = self.comp(
                self.global_name, "global", "r", self.id)
        return self.param_variable, self.param_return, self.return_

    def create_reprs(self, trial):
        self.function_repr = "<function f at 0x...>"
        return self.function_repr,

    def create_evaluations(self, trial):
        main_act = trial.main_act
        self.start = 0
        self.f_eval = self.evaluation(
            self.id, main_act, self.function_repr, 2)

        return self.f_eval


class AssignConfig(ConfigObj):

    def __init__(self, arg="a", result="b", call_line=5, duration=43):
        super(AssignConfig, self).__init__()
        self.arg = arg
        self.result = result
        self.call_line = call_line
        self.duration = duration
        self.code = None
        self.list_id = None
        self.list0_id = None
        self.write_variable_id = None
        self.read_variable_id = None
        self.arg_id = None
        self.func_variable_id = None
        self.func_id = None
        self.call_id = None
        self.result_id = None
        self.array_repr = None
        self.array0_repr = None
        self.a0comp = None
        self.start = 0
        self.list_eval = None
        self.list0_eval = None
        self.a_write_eval = None
        self.f_variable_eval = None
        self.f_func_eval = None
        self.a_read_eval = None
        self.a_arg_eval = None
        self.f_activation = None
        self.b_write_eval = None

        self.list0_member = None

        self.return_dependency = None
        self.b_dependency = None

        self.meta = None

    def define_code(self, function):
        self.code = "{0} = [1]\n{2} = {1}({0})".format(
            self.arg, function.name, self.result
        )

    def insert(self, meta, function, container_id):
        call = "{}({})".format(function.name, self.arg)
        self.meta = meta
        id_ = container_id
        self.list_id = self.comp("[1]", "list", "r", id_)
        self.list0_id = self.comp("1", "number", "r", id_)
        self.write_variable_id = self.comp(self.arg, "variable", "w", id_)
        self.read_variable_id = self.comp(self.arg, "variable", "r", id_,
                                          first_char_line=self.call_line)
        self.arg_id = self.comp(self.arg, "arg", "r", id_,
                                first_char_line=self.call_line)
        self.func_variable_id = self.comp(function.name, "variable", "r", id_,
                                          first_char_line=self.call_line)
        self.func_id = self.comp(function.name, "function", "r", id_,
                                 first_char_line=self.call_line)
        self.call_id = self.comp(call, "call", "r", id_,
                                 first_char_line=self.call_line)
        self.result_id = self.comp(self.result, "variable", "w", id_,
                                   first_char_line=self.call_line)

        return (
            self.write_variable_id, self.read_variable_id, self.arg_id,
            self.func_variable_id, self.func_id, self.call_id, self.result_id,
        )

    def create_reprs(self, trial):
        self.array_repr = "[1]"
        self.array0_repr = "1"
        return self.array_repr, self.array0_repr

    def create_evaluations(self, trial):
        self.start = 0
        main_act = trial.main_act
        function = trial.function

        self.list0_eval = self.evaluation(
            self.list0_id, main_act, self.array0_repr, 3)
        self.list_eval = self.evaluation(
            self.list_id, main_act, self.array_repr, 4)
        self.list0_member = self.member(main_act, self.list_eval, main_act, self.list0_eval,
                    key="[0]", delta=4)

        self.a_write_eval = self.evaluation(
            self.write_variable_id, main_act, self.array_repr, 4)
        self.f_variable_eval = self.evaluation(
            self.func_variable_id, main_act, function.function_repr, 5)
        self.f_func_eval = self.evaluation(
            self.func_id, main_act, function.function_repr, 6)
        self.a_read_eval = self.evaluation(
            self.read_variable_id, main_act, self.array_repr, 6)
        self.a_arg_eval = self.evaluation(
            self.arg_id, main_act, self.array_repr, 7)

        self.f_activation = self.evaluation(
            self.call_id, main_act, self.array_repr, 8 + self.duration)
        self.meta.activations_store.add(*activation_params(
            self.meta.evaluations_store[self.f_activation], self.meta.trial_id,
            function.id, name=function.name,
            start=self.start + 9
        ))

        function.x_param_eval = self.evaluation(
            function.param_variable, self.f_activation, self.array_repr, 10)
        function.x_return_eval = self.evaluation(
            function.param_return, self.f_activation, self.array_repr, 11)
        function.return_eval = self.evaluation(
            function.return_, self.f_activation, self.array_repr, 12)
        if function.global_name:
            function.global_eval = self.evaluation(
                function.global_var, self.f_activation, self.array_repr, 13)

        self.b_write_eval = self.evaluation(
            self.result_id, main_act, self.array_repr, 14)

        

        self.meta.dependencies_store.add(
            self.meta.trial_id,
            main_act, self.a_write_eval,
            main_act, self.list_eval,
            "assign", True, None, None, None)
        self.meta.dependencies_store.add(
            self.meta.trial_id,
            main_act, self.a_read_eval,
            main_act, self.a_write_eval,
            "assignment", True, None, None, None)
        self.meta.dependencies_store.add(
            self.meta.trial_id,
            main_act, self.f_variable_eval,
            main_act, function.f_eval,
            "assignment", True, None, None, None)
        self.meta.dependencies_store.add(
            self.meta.trial_id,
            main_act, self.f_func_eval,
            self.f_variable_eval, function.f_eval,
            "assign", True, None, None, None)
        self.meta.dependencies_store.add(
            self.meta.trial_id,
            main_act, self.a_arg_eval,
            main_act, self.a_read_eval,
            "assignment", True, None, None, None)
        self.meta.dependencies_store.add(
            self.meta.trial_id,
            self.f_activation, function.x_param_eval,
            main_act, self.a_arg_eval,
            "param", True, None, None, None)
        self.meta.dependencies_store.add(
            self.meta.trial_id,
            self.f_activation, function.x_return_eval,
            self.f_activation, function.x_param_eval,
            "assignment", True, None, None, None)
        if function.global_name:
            self.meta.dependencies_store.add(
                self.meta.trial_id,
                self.f_activation, function.global_eval,
                main_act, self.a_write_eval,
                "assignment", True, None, None, None)
        self.meta.dependencies_store.add(
            self.meta.trial_id,
            self.f_activation, function.return_eval,
            self.f_activation, function.x_return_eval,
            "assign", True, None, None, None)
        self.return_dependency = self.meta.dependencies_store.add(
            self.meta.trial_id,
            main_act, self.f_activation,
            self.f_activation, function.return_eval,
            "assign", True, None, None, None)
        self.b_dependency = self.meta.dependencies_store.add(
            self.meta.trial_id,
            main_act, self.b_write_eval,
            main_act, self.f_activation,
            "assing", True, None, None, None)

        return (
            self.a_write_eval, self.f_variable_eval, self.f_func_eval,
            self.a_read_eval, self.a_arg_eval, self.f_activation,
            function.x_param_eval, function.return_eval, function.return_eval,
            self.b_write_eval
        )


class AccessConfig(ConfigObj):

    def __init__(
            self,
            read_file="file.txt", write_file="file2.txt",
            read_hash="a", write_hash_before=None, write_hash_after="b",
            read_timestamp=0, write_timestamp=0):
        super(AccessConfig, self).__init__()
        self.read_file = read_file
        self.read_hash = read_hash
        self.write_file = write_file
        self.write_hash_before = write_hash_before
        self.write_hash_after = write_hash_after
        self.read_timestamp = read_timestamp
        self.write_timestamp = write_timestamp
        self.r_access = None
        self.w_access = None

    def create_accesses(self, trial):
        assign = trial.assignment
        meta = trial.meta
        self.r_access = meta.file_accesses_store.add_object(*access_params(
            meta.trial_id, name=self.read_file, checkpoint=self.read_timestamp
        ))
        self.r_access.activation_id = assign.f_activation
        self.r_access.content_hash_before = self.read_hash
        self.r_access.content_hash_after = self.read_hash
        self.w_access = meta.file_accesses_store.add_object(*access_params(
            meta.trial_id, name=self.write_file, checkpoint=self.write_timestamp
        ))
        self.w_access.activation_id = assign.f_activation
        self.w_access.mode = "w"
        self.w_access.content_hash_before = self.write_hash_before
        self.w_access.content_hash_after = self.write_hash_after

class TrialConfig(ConfigObj):
    """Configure Trial object"""
    # pylint: disable=too-many-instance-attributes

    def __init__(
            self, status="ongoing", script="main.py", docstring="block",
            year=2016, month=4, day=8, hour=1, minute=18, second=0,
            duration=65, main_duration=60, main_start=1,
            path="/home/now", bypass_modules=False):
        # pylint: disable=too-many-arguments
        super(TrialConfig, self).__init__()
        self.trial_start = datetime(
            year=year, month=month, day=day,
            hour=hour, minute=minute, second=second
        )
        self.trial_finish = self.trial_start + timedelta(seconds=duration)
        self.start = 0
        self.script = script
        self.docstring = docstring
        self.status = status
        self.bypass_modules = bypass_modules
        self.main_duration = main_duration
        self.main_start = main_start
        self.path = path
        self.trial_id = None
        self.code = None
        self.function = None
        self.assignment = None
        self.access = None
        self.main_id = None
        self.main_act = None

    def create(self, function, assignment, access):
        """Create trial and code_block"""
        restart_object_store()
        self.function = function
        self.assignment = assignment
        self.access = access
        self.meta = meta
        params = trial_params(
            script=self.script, bypass_modules=self.bypass_modules,
            path=self.path
        )
        params["start"] = self.trial_start

        self.trial_id = Trial.create(**params)
        self.meta.trial_id = self.trial_id

        self.code = "'{0}'\n{1}\n{2}".format(
            self.docstring, function.code, assignment.code
        )

        self.main_id = self.comp(self.script, "script", "w", -1)
        meta.code_blocks_store.add(*block_params(
            self.main_id, self.meta.trial_id,
            code=self.code, docstring=self.docstring
        ))
        return meta

    def update(self):
        """Update trial to set finished"""
        params = trial_update_params(main_id=self.main_id, status=self.status)
        params["finish"] = self.trial_finish
        Trial.fast_update(self.trial_id, **params)

    def create_evaluations(self):
        """Create evaluations"""
        self.main_act = self.meta.evaluations_store.add(*evaluation_params(
            self.meta.trial_id, self.main_id, -1,
            checkpoint=self.start + self.main_duration
        ))

        self.meta.activations_store.add(*activation_params(
            self.meta.evaluations_store[self.main_act],
            self.meta.trial_id, self.main_id,
            start=self.start + self.main_start
        ))

        return self.main_act

    def finished(self):
        """Create execution provenance for finished trial"""
        self.function.create_reprs(self)
        self.assignment.create_reprs(self)

        self.create_evaluations()
        self.function.create_evaluations(self)

        self.assignment.create_evaluations(self)
        self.access.create_accesses(self)


    @classmethod
    def erase(cls):
        erase_db()




def create_trial(
        trial=TrialConfig(),
        access=AccessConfig(),
        function=FuncConfig(),
        assignment=AssignConfig(),
        tag="", user="now",
        erase=False):
    """Populate database"""
    if erase:
        erase_db()
    assignment.define_code(function)
    meta = trial.create(function, assignment, access)
    trial.update()

    function.insert(meta, trial.main_id)
    function.insert_subcomponents()

    assignment.insert(meta, function, trial.main_id)

    meta.code_components_store.do_store()
    meta.code_blocks_store.do_store()

    if trial.status == "finished":
        trial.finished()
        meta.evaluations_store.do_store()
        meta.activations_store.do_store()
        meta.members_store.do_store()
        meta.dependencies_store.do_store()
        meta.file_accesses_store.do_store()

    if trial.status != "ongoing":
        if not trial.bypass_modules:
            global m1, m2, mc1, mc2
            mc1 = meta.code_components_store.add(
                meta.trial_id,
                "/home/external.py", "module", "w", 1, 0, 1, 4, -1
            )
            meta.code_blocks_store.add(mc1, meta.trial_id, "aaaa", False, None, "codeblock")
            mc2 = meta.code_components_store.add(
                meta.trial_id,
                "/home/internal.py", "module", "w", 1, 0, 1, 4, -1
            )
            meta.code_blocks_store.add(mc2, meta.trial_id, "bbbb", False, None, "codeblock")
            m1 = meta.modules_store.add(
                meta.trial_id,
                "external", "1.0.1", "/home/external.py", mc1, False, None)
            m2 = meta.modules_store.add(
                meta.trial_id,
                "internal", "", "internal.py", mc2, False, None)
            meta.code_components_store.do_store()
            meta.code_blocks_store.do_store()
            meta.modules_store.do_store()

        arguments.add(trial.trial_id, "script", trial.script)
        arguments.add(trial.trial_id, "bypass_modules", str(trial.bypass_modules))
        environment_attrs.add(trial.trial_id, "CWD", trial.path)
        environment_attrs.add(trial.trial_id, "USER", user)
        arguments.do_store()
        environment_attrs.do_store()

    if tag:
        Tag.create(**tag_params(trial.trial_id, name=tag))
        

    trial_list[trial.trial_id] = meta
    return locals()

def new_trial(*args, **kwargs):
    return create_trial(*args, **kwargs)["trial"].trial_id

