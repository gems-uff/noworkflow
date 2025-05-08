# Copyright (c) 2016 Universidade Federal Fluminense (UFF)
# Copyright (c) 2016 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""'now diff' module"""
from __future__ import (absolute_import, print_function,
                        division, unicode_literals)

import os
import difflib

from future.utils import viewitems, viewkeys
from apted import APTED

from ..ipython.converter import create_ipynb
from ..models.diff import Diff as DiffModel
from ..persistence import persistence_config, relational
from ..models.graphs.diff_graph import CONFIG
from ..utils.io import print_msg
from ..utils.cross_version import zip_longest
from ..persistence.models import Evaluation, Dependency, Activation, CodeComponent
from ..models.prov.export import OPERATIONS
from ..models.cleaning.merge import lcs
from sqlalchemy import or_, true

from .cmd_show import print_trial_relationship
from .command import NotebookCommand


def print_diff_trials(diff, skip=None):
    """Print diff of basic trial information"""
    skip = skip or set()
    for key, values in viewitems(diff.trial):
        if key not in skip:
            print("  {} changed from {} to {}".format(
                key.capitalize().replace("_", " "),
                values[0] or "<None>", values[1] or "<None>"))
    print()


def print_replaced_attributes(replaced, ignore=("id",), extra=tuple(),
                              names=None):
    """Print attributes diff"""
    names = names or {}
    for (removed, added) in replaced:
        print("  Name: {}".format(removed.name))
        output = []
        for key in viewkeys(removed.to_dict(ignore=ignore, extra=extra)):
            removed_attr = getattr(removed, key)
            added_attr = getattr(added, key)
            if removed_attr != added_attr:
                output.append("    {} changed from {} to {}".format(
                    names.get(key, key.capitalize().replace("_", " ")),
                    removed_attr or "<None>", added_attr or "<None>"))
        print("\n".join(output))
        print()


def print_replaced_environment(replaced):
    """Print environment diff"""
    for (attr_removed, attr_added) in replaced:
        print("  Environment attribute {} changed from {} to {}".format(
            attr_removed.name,
            attr_removed.value or "<None>",
            attr_added.value or "<None>"))


def print_brief(added, removed, replaced):
    """Print brief diff"""
    added_names = [access.brief for access in added]
    removed_names = [access.brief for access in removed]
    replaced_names = [rem.brief for rem, add in replaced]
    order = added_names, removed_names, replaced_names
    for column in order:
        column.sort()
    added_names.insert(0, "[Additions]")
    removed_names.insert(0, "[Removals]")
    replaced_names.insert(0, "[Changes]")
    max_column_len = [max(len(text) for text in column)
                      for column in order]

    #max_len = max(len(column) for column in order)
    for add, rem, cha in zip_longest(*order):
        add = add or ""
        rem = rem or ""
        cha = cha or ""
        print('{0: <{3}} | {1: <{4}} | {2: <{5}}'.format(
            add, rem, cha, *max_column_len))


def print_ted(diff, mode):
    if mode == "definition":
        root1 = diff.trial1.graph.definition_tree()[1]['root']
        root2 = diff.trial2.graph.definition_tree()[1]['root']
    else:
        root1 = diff.trial1.graph.no_match()[1]['root']
        root2 = diff.trial2.graph.no_match()[1]['root']
    apted = APTED(root1, root2, CONFIG)
    ted = apted.compute_edit_distance()
    print(f'{mode.capitalize()} TED:', ted)


def hide_timestamp(elements):
    """Set hide_timestamp of elements"""
    for element in elements:
        element.hide_timestamp = True


class Diff(NotebookCommand):
    """Compare the collected provenance of two trials"""

    def add_arguments(self):
        add_arg = self.add_argument
        add_arg("trial1", type=str,
                help="first trial id to be compared")
        add_arg("trial2", type=str,
                help="second trial id to be compared")
        add_arg("-m", "--modules", action="store_true",
                help="compare module dependencies")
        add_arg("-e", "--environment", action="store_true",
                help="compare environment conditions")
        add_arg("-f", "--file-accesses", action="store_true",
                help="compare read/write access to files")
        add_arg("-a", "--activations", action="store_true",
                help="compare activations")
        add_arg("-d", "--definition", action="store_true",
                help="compare definitions")
        add_arg("-t", "--hide-timestamps", action="store_true",
                help="hide timestamps")
        add_arg("-fa", "--function-activations", type=str, nargs='+',
                help="R|Compare two function activations. The first one must be from trial1 and the second one must be from trial2.\n"
                "After the functions' ids, you can specify which type of variables you want to see.\n"
                "Leave it blank: 'name', 'attribute', 'access'\n"
                "op: shows the above plus " + str(OPERATIONS).replace(")","").replace("(","") + "\n"
                "all: everything")
        add_arg("--brief", action="store_true",
                help="display a concise version of diff")
        add_arg("--dir", type=str,
                help="set project path where is the database. Default to "
                     "current directory")
        add_arg("--content-engine", type=str,
                help="set the content database engine")

    def execute(self, args):
        persistence_config.content_engine = args.content_engine
        persistence_config.connect_existing(args.dir or os.getcwd())
        if args.hide_timestamps:
            skip_in_trial = {"start", "finish", "duration_text"}
            access_extra = ("mode", "buffering", "content_hash_before",
                            "content_hash_after", "stack")
        else:
            skip_in_trial = set()
            access_extra = ("mode", "buffering", "content_hash_before",
                            "content_hash_after", "timestamp", "stack")

        diff = DiffModel(args.trial1, args.trial2)

        print_msg("trial diff:", True)
        print_diff_trials(diff, skip=skip_in_trial)

        if args.modules:
            (added, removed, replaced) = diff.modules
            if args.brief:
                print_msg("Brief modules diff", True)
                print_brief(added, removed, replaced)
            else:
                print_msg("{} modules added:".format(len(added)), True)
                print_trial_relationship(added)
                print()

                print_msg("{} modules removed:".format(len(removed)), True)
                print_trial_relationship(removed)
                print()

                print_msg("{} modules replaced:".format(len(replaced)), True)
                print_replaced_attributes(replaced)
            print()

        if args.environment:
            (added, removed, replaced) = diff.environment
            if args.brief:
                print_msg("Brief environment attributes diff", True)
                print_brief(added, removed, replaced)
            else:
                print_msg("{} environment attributes added:".format(
                    len(added)), True)
                print_trial_relationship(added, breakline="\n", other="\n  ")
                print()

                print_msg("{} environment attributes removed:".format(
                    len(removed)), True)
                print_trial_relationship(removed, breakline="\n", other="\n  ")
                print()

                print_msg("{} environment attributes replaced:".format(
                    len(replaced)), True)
                print_replaced_environment(replaced)
            print()

        if args.file_accesses:
            (added, removed, replaced) = diff.file_accesses
            self.print_file_accesses(args, access_extra, added, removed, replaced)
        
        if args.activations:
            print_ted(diff, "activations")
            print()

        if args.definition:
            print_ted(diff, "definition")
            print()

        if args.function_activations and len(args.function_activations)>=2:
            try:
                args.function_activations[0], args.function_activations[1] = int(args.function_activations[0]), int(args.function_activations[1])
            except ValueError:
                print_msg("The first two values, the functions' ids, must be integers.",True)
                exit()
                
            variable_types_to_show = None if len(args.function_activations) < 3 or (args.function_activations[2] != "op" and args.function_activations[2] != "all") else args.function_activations[2]
            
            try:
                functions_info = self.get_diff_function_info(diff.trial1.id, diff.trial2.id, args.function_activations[0], args.function_activations[1], diff.file_accesses, variable_types_to_show)
            except Exception as e:
                print_msg(e, True)
                exit()
            
            differ = difflib.Differ()
            
            trial1_variables_that_changed, trial2_variables_added, trial1_variables_removed = self.build_variables_lcs(functions_info["variables_function_trial1"], functions_info["variables_function_trial2"], differ)
            
            print_msg("Function output", True)
            for property in ["output", "arguments", "duration", "variables"]:
                didnt_change = functions_info[property+"_function_trial1"] == functions_info[property+"_function_trial2"]
                change = "didn't change" if didnt_change else "changed:"
                print_msg("The "+property+" "+change+"\n", True)
                if  not didnt_change:
                    if property == "duration":
                        functions_info[property+"_function_trial1"] = str(functions_info[property+"_function_trial1"]) + " miliseconds"
                        functions_info[property+"_function_trial2"] = str(functions_info[property+"_function_trial2"]) + " miliseconds"
                    if property == "variables":
                        [print('\n'.join(list(diff_var))) for diff_var in trial1_variables_that_changed]
                        if len(trial2_variables_added) > 0:
                            print_msg("The "+property+" added:\n", True)
                            [print(str(var)+"\n") for var in trial2_variables_added]
                        if len(trial1_variables_removed) > 0:
                            print_msg("The "+property+" removed:\n", True)
                            [print(str(var)+"\n") for var in trial1_variables_removed]
                    else:
                        diff = differ.compare(str(functions_info[property+"_function_trial1"]).splitlines(keepends=True),str(functions_info[property+"_function_trial2"]).splitlines(keepends=True))
                        print('\n'.join(list(diff)))
                    print('\n')
                
            self.print_file_accesses(args, access_extra, functions_info["file_accesses_added"], functions_info["file_accesses_removed"], functions_info["file_accesses_replaced"])

    def build_variables_lcs(self, variables_list_trial1, variables_list_trial2, differ):
        lcs_variables_result_trial1, lcs_variables_result_trial2  = lcs(variables_list_trial1, variables_list_trial2, lambda x,y: (x["name"] == y["name"]) or (difflib.SequenceMatcher(None, x["name"], y["name"]).ratio() > 0.6 and x["code_line"] == y["code_line"]))
        trial1_variables_that_changed = []
        trial1_variables_removed = []
        trial2_variables_added = []
        for i in range(len(variables_list_trial1)):
            if i in lcs_variables_result_trial1 and (str(variables_list_trial1[i]) != str(variables_list_trial2[lcs_variables_result_trial1[i]])):
                diff = differ.compare(str(variables_list_trial1[i]).splitlines(keepends=True), str(variables_list_trial2[lcs_variables_result_trial1[i]]).splitlines(keepends=True))
                trial1_variables_that_changed.append(diff)
            if i not in lcs_variables_result_trial1: trial1_variables_removed.append(variables_list_trial1[i])
        
        for j in range(len(variables_list_trial2)):
            if j not in lcs_variables_result_trial2: trial2_variables_added.append(variables_list_trial2[j])
                
        return trial1_variables_that_changed, trial2_variables_added, trial1_variables_removed

    def print_file_accesses(self, args, access_extra, added, removed, replaced):
        if args.brief:
            print_msg("Brief file access diff", True)
            print_brief(added, removed, replaced)
        else:
            if args.hide_timestamps:
                hide_timestamp(added)
                hide_timestamp(removed)
            print_msg("{} file accesses added:".format(
                    len(added)), True)
            print_trial_relationship(added)
            print()

            print_msg("{} file accesses removed:".format(
                    len(removed)), True)
            print_trial_relationship(removed)
            print()

            print_msg("{} file accesses replaced:".format(
                    len(replaced)), True)
            print_replaced_attributes(
                    replaced,
                    extra=access_extra,
                    ignore=("id", "trial_id", "function_activation_id"),
                    names={"stack": "Function"})
            

    def get_diff_function_info(self, trial1_id, trial2_id, function1_id, function2_id, file_accesses, variable_types_to_show):
        
        function_as_evaluation_trial1 = relational.session.query(Evaluation.m).filter(Evaluation.m.trial_id==trial1_id, Evaluation.m.id==function1_id).all()
        function_as_activation_trial1 = relational.session.query(Activation.m).filter(Activation.m.trial_id==trial1_id, Activation.m.id==function1_id).all()
        
        if (len(function_as_activation_trial1) <= 0) or (len(function_as_evaluation_trial1) <= 0): raise IndexError("Wrong input. There isn't a function with the id: "+str(function1_id))
        else:
            function_as_evaluation_trial1 = function_as_evaluation_trial1[0]
            function_as_activation_trial1 =  function_as_activation_trial1[0]
            
        function_as_evaluation_trial2 = relational.session.query(Evaluation.m).filter(Evaluation.m.trial_id==trial2_id, Evaluation.m.id==function2_id).all()
        function_as_activation_trial2 = relational.session.query(Activation.m).filter(Activation.m.trial_id==trial2_id, Activation.m.id==function2_id).all()
        
        if (len(function_as_activation_trial2) <= 0) or (len(function_as_evaluation_trial2) <= 0): raise IndexError("Wrong input. There isn't a function with the id: "+str(function2_id))
        else:
            function_as_evaluation_trial2 = function_as_evaluation_trial2[0]
            function_as_activation_trial2 =  function_as_activation_trial2[0]

          
        function_trial1_arguments = relational.session.query(Dependency.m).filter(Dependency.m.trial_id==trial1_id, Dependency.m.dependent_id==function_as_evaluation_trial1.id, Dependency.m.type=="argument").all()
        function_trial2_arguments = relational.session.query(Dependency.m).filter(Dependency.m.trial_id==trial2_id, Dependency.m.dependent_id==function_as_evaluation_trial2.id, Dependency.m.type=="argument").all()
        
        variable_types = [CodeComponent.m.type=="name",CodeComponent.m.type=="attribute",CodeComponent.m.type=="access"]
        if variable_types_to_show != None and variable_types_to_show.lower() == "op": [variable_types.append(CodeComponent.m.type==operation) for operation in OPERATIONS]
        variable_types = or_(true()) if variable_types_to_show != None and variable_types_to_show.lower() == "all" else or_(*variable_types)

        function_trial1_variables = relational.session.query(Evaluation.m.id, CodeComponent.m.name, Evaluation.m.repr, CodeComponent.m.type, CodeComponent.m.first_char_line, CodeComponent.m.first_char_column).filter(
            Evaluation.m.trial_id==trial1_id, Evaluation.m.activation_id==function_as_activation_trial1.id, 
            CodeComponent.m.trial_id==trial1_id, CodeComponent.m.id == Evaluation.m.code_component_id,
            variable_types).all()
        
        function_trial2_variables = relational.session.query(Evaluation.m.id, CodeComponent.m.name, Evaluation.m.repr, CodeComponent.m.type, CodeComponent.m.first_char_line, CodeComponent.m.first_char_column).filter(
            Evaluation.m.trial_id==trial2_id, Evaluation.m.activation_id==function_as_activation_trial2.id, 
            CodeComponent.m.trial_id==trial2_id, CodeComponent.m.id == Evaluation.m.code_component_id,
            variable_types).all()
        
        (added, removed, replaced) = file_accesses
        new_added = self.filter_file_accesses_diff_function(added, function_as_activation_trial1.id, function_as_activation_trial2.id)
        new_removed = self.filter_file_accesses_diff_function(removed, function_as_activation_trial1.id, function_as_activation_trial2.id)
        new_replaced = self.filter_file_accesses_diff_function(replaced, function_as_activation_trial1.id, function_as_activation_trial2.id)
          
        functions_info = {
                "output_function_trial1" : function_as_evaluation_trial1.repr,
                "output_function_trial2" : function_as_evaluation_trial2.repr,
                "arguments_function_trial1" : [relational.session.query(Evaluation.m).filter(Evaluation.m.id==argument.dependency_id, Evaluation.m.trial_id==trial1_id).all()[0].repr for argument in function_trial1_arguments],
                "arguments_function_trial2" : [relational.session.query(Evaluation.m).filter(Evaluation.m.id==argument.dependency_id, Evaluation.m.trial_id==trial2_id).all()[0].repr for argument in function_trial2_arguments],
                "duration_function_trial1" : (function_as_evaluation_trial1.checkpoint - function_as_activation_trial1.start_checkpoint) * 1000000, #miliseconds
                "duration_function_trial2" : (function_as_evaluation_trial2.checkpoint - function_as_activation_trial2.start_checkpoint) * 1000000, #miliseconds
                "variables_function_trial1" : [{"evaluation_id":variable[0],"name":variable[1],"value":variable[2],"type":variable[3],"code_line":variable[4], "code_column": variable[5]} for variable in function_trial1_variables],
                "variables_function_trial2" : [{"evaluation_id":variable[0],"name":variable[1],"value":variable[2],"type":variable[3],"code_line":variable[4], "code_column": variable[5]} for variable in function_trial2_variables],
                "file_accesses_added" : new_added,
                "file_accesses_removed": new_removed,
                "file_accesses_replaced": new_replaced
            }
        
        return functions_info
            
    def filter_file_accesses_diff_function(self, old_set, activation_id1, activation_id2):
        new_set = set()
        for file in old_set:
            if (isinstance(file, tuple)):
                print(file)
                if (file[0].activation_id == activation_id1 and file[1].activation_id == activation_id2): new_set.add(file)
            elif (file.activation_id == activation_id1) or (file.activation_id == activation_id2): new_set.add(file)
        return new_set

    def execute_export(self, args):
        persistence_config.content_engine = args.content_engine
        persistence_config.connect_existing(args.dir or os.getcwd())
        DiffModel(args.trial1, args.trial2)
        name = "Diff-{0}-{1}.ipynb".format(args.trial1, args.trial2)
        code = ("%load_ext noworkflow\n"
                "import noworkflow.now.ipython as nip\n"
                "# <codecell>\n"
                "diff = nip.Diff('{0}', '{1}')\n"
                "# diff.graph.view = 0\n"
                "# diff.graph.mode = 3\n"
                "# diff.graph.width = 500\n"
                "# diff.graph.height = 500\n"
                "# <codecell>\n"
                "diff").format(args.trial1, args.trial2)
        create_ipynb(name, code)
