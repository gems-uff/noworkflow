# Copyright (c) 2016 Universidade Federal Fluminense (UFF)
# Copyright (c) 2016 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""Trial Dot Object"""
from __future__ import (absolute_import, print_function,
                        division, unicode_literals)

import weakref

from collections import defaultdict

from copy import copy

from future.utils import viewitems, viewkeys, viewvalues

from .base import Model
from . import Activation, Variable, VariableDependency, FileAccess


CALL_SCHEMA = "#3A85B9", "box", "black"
VAR_SCHEMA = "#85CBD0", "ellipse", "black"
FILE_SCHEMA = "white", "ellipse", "black"
BLACKBOX_SCHEMA = "black", "box", "grey"
GRAYBOX_SCHEMA = "grey", "box", "black"
IMPORT_SCHEMA = "#1B2881", "box", "#7AC5F9"


TYPES = {
    "call": CALL_SCHEMA,
    "normal": VAR_SCHEMA,
    "virtual": VAR_SCHEMA,
    "param": VAR_SCHEMA,
}


def variable_id(variable):
    """Return variable identification for .dot file"""
    if isinstance(variable, FileAccess):
        return "a_{}".format(variable.id)
    act_id = variable.activation_id
    act_id = "global" if act_id == -1 else act_id
    return "v_{}_{}".format(act_id, variable.id)


def escape(string, size=55):
    """Escape string for dot file"""
    if not size:
        return ""
    if len(string) > size:
        half_size = (size - 5) // 2
        string = string[:half_size] + " ... " + string[-half_size:]
    return "" if string is None else string.replace('"', '\\"')


class TrialDot(Model):                                                           # pylint: disable=too-many-instance-attributes
    """Handle Dot export"""

    __modelname__ = "TrialDot"

    def __init__(self, trial):
        super(TrialDot, self).__init__()
        self.trial = weakref.proxy(trial)
        self.show_blackbox_dependencies = False
        self.max_depth = float("inf")
        self.mode = "simulation"
        self.rank_line = True
        self.show_accesses = True
        self.value_length = 0
        self.show_internal_use = True

        self.result = []
        self.created = set()
        self.synonyms = {}
        self.departing_arrows = {}
        self.arriving_arrows = {}
        self.variables = {v.id: v for v in self.trial.variables}

    def _add_variable(self, variable, depth, config):
        """Create variable for graph


        Arguments:
        variable -- Variable or FileAccesss object
        depth -- depth for configuring spaces in subclusters
        config -- color schema
        """
        if variable.name.startswith("_") and not self.show_internal_use:
            return
        color, shape, font = config
        var = variable_id(variable)

        value = escape(variable.value, self.value_length)
        name = escape(variable.name)

        if value == "now(n/a)":
            value = ""

        label_list = []
        if variable.line:
            label_list.append("{} ".format(variable.line))
        label_list.append(name)
        if value:
            label_list.append("\n{}".format(value))
        label = "".join(label_list)

        self.result.append("    " * depth + (
            '{var} '
            '[label="{label}"'
            ' fillcolor="{color}" fontcolor="{font}"'
            ' shape="{shape}"'
            ' style="filled"];'
        ).format(var=var, label=label, color=color, font=font, shape=shape))
        self.created.add(variable)

    def _add_all_variables(self, variables, depth):
        """Create all variables"""
        created = self.created

        for variable in variables:
            if not variable in created:
                config = TYPES.get(variable.type)
                if config:
                    self._add_variable(variable, depth, config)

    def _all_accesses(self, activation, depth):
        """Get all file accesses recursively if it reaches the maximum depth"""
        for access in activation.file_accesses:
            yield access
        if depth + 1 > self.max_depth:
            for act in activation.children:
                for access in self._all_accesses(act, depth + 1):
                    yield access

    def _add_call(self, variable, depth, recursive_function):
        """Check if call is valid for subcluster
        If it is, create a subcluster and call <recursive_function>

        Return return_ variable and type

        There are five possible type:
        fake -- indicates that variable is a fake call (no cluster)
        c_call -- indicates that variable is a c_call (no cluster)
        just_return -- indicates that call has only a return node (no cluster)
        max_depth -- indicates that it reached the max depth (no cluster)
        subgraph -- user defined call within depth (create cluster)
        """

        return_ = variable.return_dependency
        if not return_:
            # Fake call
            return None, "fake"
        activation_id = variable.activation_id
        new_activation_id = return_.activation_id
        if self.show_accesses:
            for access in self._all_accesses(return_.activation, depth):
                access.value = ""
                access.line = ""
                self._add_variable(access, depth, FILE_SCHEMA)
                if set("ra+") & set(access.mode):
                    self.departing_arrows[variable][access] = "dashed"
                    self.arriving_arrows[access][variable] = "dashed"
                if set("wxa+") & set(access.mode):
                    self.arriving_arrows[variable][access] = "dashed"
                    self.departing_arrows[access][variable] = "dashed"
        if new_activation_id == activation_id:
            # c_call
            variable.value = return_.value
            self.synonyms[return_] = variable
            return None, "c_call"
        if len(list(return_.activation.variables)) == 1:
            # Just return. Maybe c_call
            variable.value = return_.value
            self.synonyms[return_] = variable
            return None, "just_return"
        ndepth = depth + 1
        if ndepth > self.max_depth:
            # max depth
            variable.value = return_.value
            self.synonyms[return_] = variable
            return None, "max_depth"
        trial_id = variable.trial_id
        new_activation = Activation((trial_id, new_activation_id))
        result = self.result
        result.append(
            "    " * depth +
            "subgraph cluster_{}  {{".format(new_activation_id)
        )

        result.append("    " * ndepth + 'color="#3A85B9";')
        result.append("    " * ndepth + 'fontsize=30;')
        result.append("    " * ndepth +
                      'label = "{}";'.format(variable.name))

        if any([any(return_.dependencies_as_source),
                any(variable.dependencies_as_target)]):

            self._add_variable(return_, ndepth, VAR_SCHEMA)
            self.synonyms[variable] = return_

        self._add_all_variables(new_activation.param_variables, ndepth)

        recursive_function(new_activation, ndepth)
        self._prepare_rank(new_activation, ndepth)
        result.append("    " * depth + "}")
        return return_, "subgraph"

    def _prepare_rank(self, activation, depth):
        """Group variables by line"""
        if self.rank_line:
            result = self.result
            created = self.created
            by_line = defaultdict(list)
            for variable in activation.variables:
                if variable in created:
                    by_line[variable.line].append(variable)

            for variables in viewvalues(by_line):
                result.append(
                    "    " * depth + "{rank=same " +
                    " ".join(variable_id(var) for var in variables) + "}")

    def _create_dependencies(self, skip_arg=True):
        """Load dependencies from database into a graph"""
        departing_arrows = self.departing_arrows
        arriving_arrows = self.arriving_arrows
        synonyms = self.synonyms
        variables = self.variables

        for sid, tid in VariableDependency.fast_load_by_trial(self.trial.id):
            osource = variables[sid]
            source = synonyms.get(osource, osource)
            otarget = variables[tid]
            target = synonyms.get(otarget, otarget)
            typ = ""
            if (osource.type == otarget.type == "--blackbox--" and
                    not self.show_blackbox_dependencies):
                continue

            if "box--" in target.type:
                typ = "dashed"
            if source != target and (not skip_arg or osource.type != "arg"):
                departing_arrows[source][target] = typ
                arriving_arrows[target][source] = typ

    def _fix_dependencies(self):
        """Propagate dependencies, removing missing nodes"""
        created = self.created
        synonyms = self.synonyms
        arriving_arrows = self.arriving_arrows
        departing_arrows = self.departing_arrows

        removed = (
            set(viewvalues(self.variables))
            - created
            - set(viewkeys(synonyms))
        )
        for variable in removed:
            variable_is_box = "box--" in variable.name
            for source, typ_sv in viewitems(arriving_arrows[variable]):
                if (variable_is_box and "box--" in source.name and
                        not self.show_blackbox_dependencies):
                    continue
                for target, typ_vt in viewitems(departing_arrows[variable]):
                    if variable_is_box and source.type == target.type == "arg":
                        continue
                    typ = typ_sv or typ_vt
                    if not typ and not variable_is_box:
                        typ = "dashed"

                    #del arriving_arrows[target][variable]
                    #del departing_arrows[variable][target]
                    departing_arrows[source][target] = typ
                    arriving_arrows[target][source] = typ
            del arriving_arrows[variable]
            for target, typ_vt in viewitems(departing_arrows[variable]):
                if (variable_is_box and "box--" in target.name and
                        not self.show_blackbox_dependencies):
                    continue
                for source, typ_sv in viewitems(arriving_arrows[variable]):
                    if variable_is_box and source.type == target.type == "arg":
                        continue
                    typ = typ_sv or typ_vt
                    if not typ and not variable_is_box:
                        typ = "dashed"
                    #del arriving_arrows[variable][source]
                    #del departing_arrows[source][variable]
                    departing_arrows[source][target] = typ
                    arriving_arrows[target][source] = typ
            del departing_arrows[variable]

    def _show_dependencies(self):
        """Show dependencies"""
        result = self.result
        created = self.created
        departing_arrows = self.departing_arrows

        self._fix_dependencies()

        for source, targets in viewitems(departing_arrows):
            if source not in created:
                continue
            for target, style in viewitems(targets):
                if target not in created or source == target:
                    continue

                result.append(('    {} -> {} [style="{}"];').format(
                    variable_id(source), variable_id(target), style
                ))

    def _export_text(self):
        """Export graph text"""
        self.erase()
        result = self.result
        result.append("digraph dependency {")
        result.append("  rankdir=RL;")
        result.append("  node[fontsize=20]")
        getattr(self, self.mode)()
        result.append("}")
        return result

    def _dataflow(self, function):
        """Create dataflow graph"""
        synonyms = self.synonyms
        variables = self.variables
        for activation in self.trial.initial_activations:
            function(activation)
            self._prepare_rank(activation, 1)


        arg_orginal = Variable.fast_arg_and_original(self.trial.id)
        for arg_id, original_id in arg_orginal:
            synonyms[variables[arg_id]] = variables[original_id]

        self._create_dependencies()
        self._show_dependencies()

    def _simulation_activation(self, activation, depth=1):
        """Export simulation activation"""
        for variable in activation.variables:
            if (variable.type == "call" and
                    self._add_call(variable, depth,
                                   self._simulation_activation)[0]):
                continue

            config = TYPES.get(variable.type)
            if config:
                self._add_variable(variable, depth, config)

    def _prospective_activation(self, activation, depth=1):
        """Export prospective activation"""
        # ToDo: param dependencies
        for variable in activation.no_param_variables:
            if variable.type == "call":
                return_, mode = self._add_call(variable, depth,
                                               self._prospective_activation)
                if not return_:
                    config = TYPES.get(variable.type)
                    self._add_variable(variable, depth, config)

                if mode == "fake":
                    box = variable.box_dependency
                    self._add_all_variables(box.dependencies, depth)

                elif mode in ("c_call", "just_return"):
                    return_ = variable.return_dependency
                    box = return_.box_dependency
                    if box:
                        self._add_all_variables(box.dependencies, depth)

                elif mode == "max_depth":
                    return_ = variable.return_dependency
                    for var in return_.activation.param_variables:
                        self._add_all_variables(var.dependencies, depth)
                elif mode == "subgraph":
                    for var in return_.activation.param_variables:
                        self._add_all_variables(var.dependencies, depth)

                self._add_all_variables(variable.dependents, depth)

    def simulation(self):
        """Create simulation graph"""
        self._dataflow(self._simulation_activation)

    def prospective(self):
        """Create prospective graph"""
        self._dataflow(self._prospective_activation)

    def dependency(self):
        """Create dependency graph"""
        types = copy(TYPES)
        types["import"] = IMPORT_SCHEMA
        types["--blackbox--"] = BLACKBOX_SCHEMA
        types["--graybox--"] = GRAYBOX_SCHEMA

        for variable in viewvalues(self.variables):
            config = types.get(variable.type)
            if config:
                self._add_variable(variable, 1, config)
            else:
                self._add_variable(variable, 1, VAR_SCHEMA)

        self._create_dependencies(skip_arg=False)
        self._show_dependencies()




    def erase(self):
        """Erase graph"""
        self.result = []
        self.created = set()
        self.synonyms = {}
        self.departing_arrows = defaultdict(dict)
        self.arriving_arrows = defaultdict(dict)

    def export_text(self):
        """Export facts from trial as text"""
        return "\n".join(self._export_text())

    def _repr_png_(self):
        ipython = get_ipython()
        return ipython.run_cell_magic('dot', '', self.export_text())
