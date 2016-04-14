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
from ...now.persistence.lightweight import ValueLW, CompartmentLW
from ...now.persistence.lightweight import DependencyLW, FileAccessLW
from ...now.persistence.lightweight import ModuleLW, ModuleDependencyLW
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
    global file_accesses, values, compartments, modules, module_dependencies
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
    values = meta.values_store
    compartments = meta.compartments_store
    modules = meta.modules_store
    modules.id = ModuleLW.model.id_seq()
    module_dependencies = meta.module_dependencies_store
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
    relational.session.execute(ValueLW.model.t.delete())
    relational.session.execute(CompartmentLW.model.t.delete())
    relational.session.execute(ModuleLW.model.t.delete())
    relational.session.execute(ModuleDependencyLW.model.t.delete())
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
    return relational.session.execute(
        select([Trial.m]).where(Trial.m.id == id_)
    ).first()


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


def component_params(name="main.py", type_="script", mode="w",
                     first_char_line=1, first_char_column=0,
                     last_char_line=1, last_char_column=7,
                     container_id=None, ):
    """Return default component params"""
    return [name, type_, mode, first_char_line, first_char_column,
            last_char_line, last_char_column, container_id]


def block_params(id_, code="'block'", docstring="block"):
    """Return default code block params"""
    return [id_, code, docstring]


def evaluation_params(code_component_id, activation_id, value_id=-1,
                      year=2016, month=4, day=8, hour=1, minute=19, second=5):
    """Return evaluation params"""
    moment = datetime(
        year=year, month=month, day=day,
        hour=hour, minute=minute, second=second
    )
    return [moment, code_component_id, activation_id, value_id]


def activation_params(id_, code_block_id, name="main.py",
                      year=2016, month=4, day=8, hour=1, minute=18, second=5):
    """Return activation params"""
    start = datetime(
        year=year, month=month, day=day,
        hour=hour, minute=minute, second=second
    )
    return [id_, name, start, code_block_id]

def value_params(value="<class 'type'>", type_id=1):
    """Return value params"""
    return [value, type_id]


def compartment_params(whole_id, part_id, name="[0]",
                       year=2016, month=4, day=8, hour=1, minute=19, second=5):
    """Return compartment params"""
    moment = datetime(
        year=year, month=month, day=day,
        hour=hour, minute=minute, second=second
    )
    return [name, moment, whole_id, part_id]

def access_params(name="file.txt"):
    return [name]

def _add_component(name, type_, mode, container_id):
    return components.add(*component_params(
        name=name, type_=type_, mode=mode, container_id=container_id
    ))


def _add_value(value, type_id):
    return values.add(*value_params(value=value, type_id=type_id))


def _add_evaluation(code_component_id, activation_id, value_id, second):
    return evaluations.add(*evaluation_params(
        code_component_id, activation_id, value_id=value_id, second=second
    ))


class ConfigObj(object):

    def comp(self, name, type_, mode, container_id, **kwargs):
        meta = self.meta
        return meta.code_components_store.add(*component_params(
            name=name, type_=type_, mode=mode, container_id=container_id,
            **kwargs
        ))

    def value(self, value, type_id):
        meta = self.meta
        return meta.values_store.add(*value_params(
            value=value, type_id=type_id))

class FuncConfig(ConfigObj):

    def __init__(self, name="f", first_line=1, first_column=0,
                 last_line=2, last_column=12, param="x", docstring=None):
        self.name = name
        self.first_char_line = first_line
        self.first_char_column = first_column
        self.last_char_line = last_line
        self.last_char_column = last_column
        self.param = param
        self.code = "def {0}({1}):\n".format(name, param)
        self.docstring = docstring
        if docstring is not None:
            self.code += "    '{}'\n".format(docstring)
        self.code += "    return {}".format(param)

        self.id = -1
        self.param_variable = None
        self.param_return = None
        self.return_ = None
        self.function_type = None
        self.function_value = None

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
            self.id, code=self.code, docstring=self.docstring
        ))
        return self.id

    def insert_subcomponents(self):
        self.param_variable = self.comp(self.param, "param", "w", self.id)
        self.param_return = self.comp(self.param, "variable", "r", self.id)
        self.return_ = self.comp("return", "return", "r", self.id)
        return self.param_variable, self.param_return, self.return_

    def create_values(self, type_value_id):
        self.function_type = self.value("<class 'function'>", type_value_id)
        self.function_value = self.value("<function f at 0x...>",
                                         self.function_type)
        return self.function_type, self.function_value


class AssignConfig(ConfigObj):

    def __init__(self, arg="a", result="b"):
        self.arg = arg
        self.result = result
        self.code = None
        self.write_variable_id = None
        self.read_variable_id = None
        self.arg_id = None
        self.func_variable_id = None
        self.func_id = None
        self.call_id = None
        self.result_id = None
        self.list_type = None
        self.array_value = None
        self.int_type = None
        self.array0_value = None
        self.a0comp = None

    def define_code(self, function):
        self.code = "{0} = [1]\n{2} = {1}({0})".format(
            self.arg, function.name, self.result
        )


    def insert(self, meta, function, container_id):
        call = "{}({})".format(function.name, self.arg)
        self.meta = meta
        id_ = container_id
        self.write_variable_id = self.comp(self.arg, "variable", "w", id_)
        self.read_variable_id = self.comp(self.arg, "variable", "r", id_)
        self.arg_id = self.comp(self.arg, "arg", "r", id_)
        self.func_variable_id = self.comp(function.name, "variable", "r", id_)
        self.func_id = self.comp(function.name, "function", "r", id_)
        self.call_id = self.comp(call, "call", "r", id_)
        self.result_id = self.comp(self.result, "variable", "w", id_)

        return (
            self.write_variable_id, self.read_variable_id, self.arg_id,
            self.func_variable_id, self.func_id, self.call_id, self.result_id,
        )

    def create_values(self, type_value_id):
        self.list_type = self.value("<class 'list'>", type_value_id)
        self.array_value = self.value("[1]", self.list_type)
        self.int_type = self.value("<class 'int'>", type_value_id)
        self.array0_value = self.value("1", self.int_type)
        self.a0comp = self.meta.compartments_store.add(*compartment_params(
            self.array_value, self.array0_value
        ))
        return (
            self.list_type, self.array_value, self.int_type, self.array0_value,
        )


class TrialConfig(ConfigObj):

    def __init__(self, status="ongoing", script="main.py", docstring="block",
            year=2016, month=4, day=8, hour=1, minute=18, second=0,
            duration=65, path="/home/now", bypass_modules=False):
        self.start =  datetime(
            year=year, month=month, day=day,
            hour=hour, minute=minute, second=second
        )
        self.finish = self.start + timedelta(seconds=duration)
        self.script = script
        self.docstring = docstring
        self.status = status
        self.bypass_modules = bypass_modules
        self.path = path
        self.trial_id = None
        self.code = None
        self.function = None
        self.assignment = None
        self.main_id = None
        self.type_value_id = None

    def create(self, function, assignment):
        restart_object_store()
        self.function = function
        self.assignment = assignment
        self.meta = meta
        params = trial_params(
            script=self.script, bypass_modules=self.bypass_modules,
            path=self.path
        )
        params["start"] = self.start

        self.trial_id = Trial.store(**params)

        self.code = "'{0}'\n{1}\n{2}".format(
            self.docstring, function.code, assignment.code
        )

        self.main_id = self.comp(self.script, "scripẗ", "w", -1)
        meta.code_blocks_store.add(*block_params(
            self.main_id, code=self.code, docstring=self.docstring
        ))
        return meta

    def update(self):
        params = trial_update_params(main_id=self.main_id, status=self.status)
        params["finish"] = self.finish
        Trial.fast_update(self.trial_id, **params)


    def create_values(self):
        self.type_value_id = meta.values_store.add(*value_params())
        type_object = meta.values_store[self.type_value_id]
        type_object.type_id = self.type_value_id
        return self.type_value_id

    def finished(self):
        self.create_values()


    @classmethod
    def erase(cls):
        erase_db()




def create_trial(
        trial=TrialConfig(),
        read_file="file.txt", write_file="file2.txt",
        read_hash="a", write_hash_before=None, tag="",
        write_hash_after="b",  user="now",
        function=FuncConfig(),
        assignment=AssignConfig(),
        erase=False):
    """Populate database"""
    if erase:
        erase_db()
    assignment.define_code(function)
    meta = trial.create(function, assignment)
    trial.update()

    function_component_id = function.insert(meta, trial.main_id)
    subcomponents = function.insert_subcomponents()
    xparam, xreturn, return_ = subcomponents

    awrite, aread, aarg, fvar, ffunction, facall, bwrite = assignment.insert(meta, function, trial.main_id)

    components.fast_store(trial.trial_id)
    blocks.fast_store(trial.trial_id)

    if trial.status == "finished":
        vtype = trial.create_values()
        ftype, fvalue = function.create_values(vtype)
        ltype, avalue, itype, a0value = assignment.create_values(vtype)

        main_act = evaluations.add(*evaluation_params(trial.main_id, -1, second=59))
        activations.add(*activation_params(main_act, trial.main_id, second=1))
        feval = _add_evaluation(function_component_id, main_act, fvalue, 2)
        aweval = _add_evaluation(awrite, main_act, avalue, 3)
        fvareval = _add_evaluation(fvar, main_act, fvalue, 4)
        ffunceval = _add_evaluation(ffunction, main_act, fvalue, 5)
        areadeval = _add_evaluation(aread, main_act, avalue, 5)
        aargeval = _add_evaluation(aarg, main_act, avalue, 6)
        faceval = _add_evaluation(facall, main_act, avalue, 50)
        activations.add(*activation_params(
            faceval, function_component_id, second=7
        ))
        xpreval = _add_evaluation(xparam, faceval, avalue, 8)
        xreteval = _add_evaluation(xreturn, faceval, avalue, 9)
        returneval = _add_evaluation(return_, faceval, avalue, 10)
        bwriteeval = _add_evaluation(bwrite, main_act, avalue, 11)

        dependencies.add(main_act, areadeval, main_act, aweval, "assignment")
        dependencies.add(main_act, fvareval, main_act, feval, "assignment")
        dependencies.add(main_act, ffunceval, fvareval, feval, "bind")
        dependencies.add(main_act, aargeval, main_act, areadeval, "bind")
        dependencies.add(faceval, xpreval, main_act, aargeval, "bind")
        dependencies.add(faceval, xreteval, faceval, xpreval, "assignment")
        dependencies.add(faceval, returneval, faceval, xreteval, "bind")
        dependencies.add(main_act, faceval, faceval, returneval, "bind")
        dependencies.add(main_act, bwriteeval, main_act, faceval, "bind")

        r_access = file_accesses.add_object(*access_params(name=read_file))
        r_access.activation_id = faceval
        r_access.content_hash_before = read_hash
        r_access.content_hash_after = read_hash
        w_access = file_accesses.add_object(*access_params(name=write_file))
        w_access.activation_id = faceval
        w_access.mode = "w"
        w_access.content_hash_before = write_hash_before
        w_access.content_hash_after = write_hash_after



        values.fast_store(trial.trial_id)
        compartments.fast_store(trial.trial_id)
        evaluations.fast_store(trial.trial_id)
        activations.fast_store(trial.trial_id)
        dependencies.fast_store(trial.trial_id)
        file_accesses.fast_store(trial.trial_id)

    if trial.status != "ongoing":
        if not trial.bypass_modules:
            if not count(ModuleLW.model):
                global m1, m2
                m1 = modules.add("external", "1.0.1", "/home/external.py",
                                 "aaaa")
                m2 = modules.add("internal", "", "internal.py", "bbbb")

                modules.fast_store(trial.trial_id)
            module_dependencies.add(m1)
            module_dependencies.add(m2)
            module_dependencies.fast_store(trial.trial_id)

        arguments.add("script", trial.script)
        arguments.add("bypass_modules", str(trial.bypass_modules))
        environment_attrs.add("CWD", trial.path)
        environment_attrs.add("USER", user)
        arguments.fast_store(trial.trial_id)
        environment_attrs.fast_store(trial.trial_id)

    if tag:
        Tag.create(**tag_params(trial.trial_id, name=tag))

    trial_list[trial.trial_id] = meta
    return locals()

def new_trial(*args, **kwargs):
    return create_trial(*args, **kwargs)["trial"].trial_id

