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
from ...now.persistence import relational
from ...now.collection.metadata import Metascript


trial_list = {}
meta = None

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
    module_dependencies = meta.module_dependencies_store
    environment_attrs = meta.environment_attrs_store
    arguments = meta.arguments_store

restart_object_store()


def erase_database():
    """Remove all rows from database"""
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
    restart_object_store()


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


def head_count():
    """Count Head tuples"""
    return relational.session.query(func.count(Head.m.id)).scalar()

def tag_count():
    """Count Tag tuples"""
    return relational.session.query(func.count(Tag.m.id)).scalar()



def tag_params(trial_id, name="tag", type_="AUTO", minute=20):
    """Return default tag params"""
    return {
        "trial_id": trial_id,
        "name": name,
        "type_": type_,
        "timestamp": datetime(year=2016, month=4, day=8, hour=1, minute=minute)
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


def populate_trial(year=2016, month=4, day=8, hour=1, minute=18, second=0,
                   duration=65, script="main.py", docstring="block",
                   status="ongoing", bypass_modules=False,
                   read_file="file.txt", write_file="file2.txt",
                   read_hash="a", write_hash_before=None, tag="",
                   write_hash_after="b", path="/home/now", user="now"):
    """Populate database"""
    restart_object_store()
    params = trial_params(script=script, bypass_modules=bypass_modules,
                          path=path)
    params["start"] = datetime(
        year=year, month=month, day=day,
        hour=hour, minute=minute, second=second
    )

    trial_id = Trial.store(**params)

    function_code = "def f(x):\n    return x"
    code = "'{}'\n{}\na = [1]\nb = f(a)".format(docstring, function_code)

    main_id = _add_component(script, "script", "w", -1)
    blocks.add(*block_params(main_id, code=code, docstring=docstring))

    params2 = trial_update_params(main_id=main_id, status=status)
    params2["finish"] = params["start"] + timedelta(seconds=duration)
    Trial.fast_update(trial_id, **params2)

    fid = _add_component("f", "function_def", "w", main_id)
    blocks.add(*block_params(fid, code=function_code, docstring=None))
    xparam = _add_component("x", "param", "w", fid)
    xreturn = _add_component("x", "variable", "r", fid)
    return_ = _add_component("return", "return", "r", fid)
    awrite = _add_component("a", "variable", "w", main_id)
    aread = _add_component("a", "variable", "r", main_id)
    aarg = _add_component("a", "arg", "r", main_id)
    fvar = _add_component("f", "variable", "r", main_id)
    ffunction = _add_component("f", "function", "r", main_id)
    facall = _add_component("f(a)", "call", "r", main_id)
    bwrite = _add_component("b", "variable", "w", main_id)

    components.fast_store(trial_id)
    blocks.fast_store(trial_id)

    if status == "finished":
        vtype = values.add(*value_params())
        type_object = values[vtype]
        type_object.type_id = vtype
        ftype = _add_value("<class 'function'>", vtype)
        fvalue = _add_value("<function f at 0x...>", ftype)
        ltype = _add_value("<ckass 'list'>", vtype)
        avalue = _add_value("[1]", ltype)
        itype = _add_value("<class 'int'>", vtype)
        a0value = _add_value("1", itype)
        compartments.add(*compartment_params(avalue, a0value))

        main_act = evaluations.add(*evaluation_params(main_id, -1, second=59))
        activations.add(*activation_params(main_act, main_id, second=1))
        feval = _add_evaluation(fid, main_act, fvalue, 2)
        aweval = _add_evaluation(awrite, main_act, avalue, 3)
        fvareval = _add_evaluation(fvar, main_act, fvalue, 4)
        ffunceval = _add_evaluation(ffunction, main_act, fvalue, 5)
        areadeval = _add_evaluation(aread, main_act, avalue, 5)
        aargeval = _add_evaluation(aarg, main_act, avalue, 6)
        faceval = _add_evaluation(facall, main_act, avalue, 50)
        activations.add(*activation_params(faceval, fid, second=7))
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



        values.fast_store(trial_id)
        compartments.fast_store(trial_id)
        evaluations.fast_store(trial_id)
        activations.fast_store(trial_id)
        dependencies.fast_store(trial_id)
        file_accesses.fast_store(trial_id)

    if status != "ongoing":
        if not bypass_modules:
            if modules.id <= 0:
                modules.add("external", "1.0.1", "/home/external.py", "aaaa")
                modules.add("internal", "", "internal.py", "bbbb")

                modules.fast_store(trial_id)
            module_dependencies.add(1)
            module_dependencies.add(2)
            module_dependencies.fast_store(trial_id)

        arguments.add("script", script)
        arguments.add("bypass_modules", str(bypass_modules))
        environment_attrs.add("CWD", path)
        environment_attrs.add("USER", user)
        arguments.fast_store(trial_id)
        environment_attrs.fast_store(trial_id)

    if tag:
        Tag.create(**tag_params(trial_id, name=tag))

    trial_list[trial_id] = meta
    return trial_id
