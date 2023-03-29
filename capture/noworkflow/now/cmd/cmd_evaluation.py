# Copyright (c) 2021 Universidade Federal Fluminense (UFF)
# Copyright (c) 2021 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
""""now list" command"""
from __future__ import (absolute_import, print_function,
                        division, unicode_literals)

import os

from ..persistence.models import Trial
from ..persistence import persistence_config, relational
from ..persistence.models import Evaluation as EvaluationM, CodeComponent, Activation
from ..persistence.models.base import proxy, proxy_gen
from ..utils.io import print_msg

from .command import Command


def add_query_arguments(add_arg, prefix="", add_trial=True):
    """Add query command to subparser"""
    if add_trial:
        add_arg("-t", "--trial", type=str, nargs="?", dest=prefix + "trial",
                help="trial id or none for last trial")
    add_arg("-l", "--line", type=int, dest=prefix + "line",
            help="line number")
    add_arg("--column", type=int, dest=prefix + "column",
            help="column number")
    add_arg("-n", "--cell", type=str, dest=prefix + "cell",
            help="cell number")
    add_arg("-m", "--mode", type=str, dest=prefix + "mode",
            help="write (w), read(r), delete(d), parameter(p), or augmented assignments(w+, r+)")
    add_arg("-c", "--code", type=str, dest=prefix + "code",
            help="code component definition")
    add_arg("-v", "--value", type=str, dest=prefix + "value",
            help="evaluation result")
    add_arg("--cid", type=int, dest=prefix + "cid",
            help="code component id")
    add_arg("--eid", type=int, dest=prefix + "eid",
            help="evaluation id")
    add_arg("--aid", type=int, dest=prefix + "aid",
            help="activation id")
    add_arg("-i", "--index", type=int, dest=prefix + "index",
            help="select a single evaluation that matches the criteria")


def query_evaluations(args, prefix=""):
    """Evaluate subparser query command"""
    atrial = getattr(args, prefix + 'trial', None) 
    trial = Trial(trial_ref=atrial)
    filters = [
        EvaluationM.m.trial_id == trial.id
    ]
    query = relational.session.query(EvaluationM.m).join(CodeComponent.m, (
        (EvaluationM.m.trial_id == CodeComponent.m.trial_id)
        & (EvaluationM.m.code_component_id == CodeComponent.m.id)
    )) 
    line = getattr(args, prefix + 'line', None) 
    if line is not None:
        filters.append(CodeComponent.m.first_char_line >= line)
        filters.append(CodeComponent.m.last_char_line <= line)
    column = getattr(args, prefix + 'column', None)
    if column is not None:
        filters.append(CodeComponent.m.first_char_column >= column)
        filters.append(CodeComponent.m.last_char_column <= column)
    cell = getattr(args, prefix + 'cell', None)
    if cell is not None:
        query = query.join(Activation.m, (
            (Activation.m.trial_id == EvaluationM.m.trial_id)
            & (Activation.m.id == EvaluationM.m.activation_id)
        ))
        filters.append(Activation.m.name.like('<ipython-input-{}%'.format(cell)))
    code = getattr(args, prefix + 'code', None)
    if code is not None:
        filters.append(CodeComponent.m.name == code)
    mode = getattr(args, prefix + 'mode', None)
    if mode is not None:
        filters.append(CodeComponent.m.mode == mode)
    cid = getattr(args, prefix + 'cid', None)
    if cid is not None:
        filters.append(CodeComponent.m.id == cid)
    value = getattr(args, prefix + 'value', None)
    if value is not None:
        filters.append(EvaluationM.m.repr == value)
    eid = getattr(args, prefix + 'eid', None)
    if eid is not None:
        filters.append(EvaluationM.m.id == eid)
    aid = getattr(args, prefix + 'aid', None)
    if aid is not None:
        filters.append(EvaluationM.m.activation_id == aid)
    evaluations = query.filter(*filters)
    result = list(evaluations)
    argindex = getattr(args, prefix + 'index', None)
    if argindex is not None:
        index = argindex- 1 # 1-based index
        if index > len(result):
            result = []
        else:
            result = [result[index]]
    return result


def add_display_subparser(subparsers):
    display = subparsers.add_parser('display')
    display.add_argument("-c", "--show-code-component", action="store_true")
    display.add_argument("-v", "--show-value", action="store_true")
    display.add_argument("-t", "--show-checkpoint", action="store_true")
    display.add_argument("-a", "--show-activation", action="store_true")
    display.add_argument("-p", "--show-position", action="store_true")
    return display


def add_wdf_subparser(subparsers):
    wdf = subparsers.add_parser('wdf', help="find was derived from relationships")
    add_query_arguments(wdf.add_argument, prefix="wdf_")
    wdf.set_defaults(wdf=True)
    return wdf


class Evaluation(Command):
    """Query evaluation and its dependencies"""

    def add_arguments(self):
        add_arg = self.add_argument
        
        add_query_arguments(add_arg)
                
        add_arg("--dir", type=str,
                help="set project path where is the database. Default to "
                     "current directory")
        add_arg("--content-engine", type=str,
                help="set the content database engine")

        subparsers = self.parser.add_subparsers()
        
        display = add_display_subparser(subparsers)
        dsubparsers = display.add_subparsers()
        add_wdf_subparser(dsubparsers)
        
        wdf = add_wdf_subparser(subparsers)
        wsubparsers = wdf.add_subparsers()
        add_display_subparser(wsubparsers)

    def display_evaluation(self, eva, args, prefix="- ", spaces="  "):
        act = eva.activation
        code = eva.code_component
        extra = ""
        if act and act.name.startswith("<ipython-input-"):
            extra = "In[{}] ".format(act.name.split("-")[2])
        print("{}{}{} {} (A{} E{})".format(
            prefix, extra,
            code.first_char_line, code.name,
            eva.activation_id, eva.id 
        ))
        if getattr(args, 'show_code_component', False):
            print("{}Code Component: {} Mode: {}".format(spaces, code.id, code.mode))
        if getattr(args, 'show_position', False):
            print("{}Position: ({}, {}) - ({}, {})".format(
                spaces, code.first_char_line, code.first_char_column,
                code.last_char_line, code.last_char_column
            ))
        if getattr(args, 'show_value', False):
            print("{}Value: {}".format(spaces, eva.repr))
        if getattr(args, 'show_checkpoint', False):
            print("{}Moment: {}".format(spaces, eva.moment))
        if act and getattr(args, 'show_activation', False):
            print("{}Activation: {} (A{} E{})".format(spaces, act.name, act.this_evaluation.activation_id, act.id))


    def execute(self, args):
        persistence_config.content_engine = args.content_engine
        persistence_config.connect_existing(args.dir or os.getcwd())
        
        result = query_evaluations(args)

        if not result:
            print("No evaluation found")
            return

        check_dependencies = []
        if getattr(args, 'wdf', False):
            if args.trial and not args.wdf_trial:
                args.wdf_trial = args.trial
            check_dependencies = list(proxy_gen(query_evaluations(args, prefix="wdf_")))

        print("Found {} evaluation(s):".format(len(result)))
        for eva in result:
            eva = proxy(eva)
            self.display_evaluation(eva, args)

            derived_from = eva.was_derived_from(check_dependencies, distinguish=True)
            for other, derived in derived_from.items():
                if derived:
                    self.display_evaluation(other, args, prefix="  WasDerivedFrom: ", spaces="    ")
