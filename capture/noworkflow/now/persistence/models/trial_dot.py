# Copyright (c) 2016 Universidade Federal Fluminense (UFF)
# Copyright (c) 2016 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""Trial Dot Object"""
from __future__ import (absolute_import, print_function,
                        division, unicode_literals)

import weakref

from collections import defaultdict

from future.utils import viewitems, viewkeys, viewvalues

from .base import Model
from . import Activation, Variable, VariableDependency, FileAccess


ITERATOR_SCHEMA = "#1B2881", "box", "#7AC5F9"
CALL_SCHEMA = "#3A85B9", "box", "black"
VAR_SCHEMA = "#85CBD0", "ellipse", "black"
FILE_SCHEMA = "white", "ellipse", "black"

TYPES = {
    "iterator": ITERATOR_SCHEMA,
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
    if not size:
        return ""
    if len(string) > size:
        s = (size - 5) // 2
        string = string[:s] + " ... " + string[-s:]
    return "" if string is None else string.replace('"', '\\"')


class TrialDot(Model):
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

        self.result = []
        self.created = set()
        self.synonyms = {}
        self.departing_arrows = {}
        self.arriving_arrows = {}
        self.variables = {v.id: v for v in self.trial.variables}

    def _add_variable(self, variable, depth, config):
        color, shape, font = config                                              # pylint: disable=unused-variable
        var = variable_id(variable)

        value = escape(variable.value, self.value_length)
        name = escape(variable.name)

        if value == "now(n/a)":
            value = ""


        label = []
        if variable.line:
            label.append("{} ".format(variable.line))
        label.append(name)
        if value:
            label.append("\n{}".format(value))
        label = "".join(label)

        self.result.append("    " * depth + (
            '{var} '
            '[label="{label}"'
            ' fillcolor="{color}" fontcolor="{font}"'
            ' shape="{shape}"'
            ' style="filled"];'
        ).format(**locals()))
        self.created.add(variable)

    def _all_accesses(self, activation, depth):
        for access in activation.file_accesses:
            yield access
        if depth + 1 > self.max_depth:
            for act in activation.children:
                for access in self._all_accesses(act, depth + 1):
                    yield access

    def _add_call(self, variable, depth):

        _return = variable.return_dependency
        if not _return:
            # Fake call
            return False
        activation_id = variable.activation_id
        new_activation_id = _return.activation_id
        if self.show_accesses:
            for access in self._all_accesses(_return.activation, depth):
                #print(access)
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
            variable.value = _return.value
            self.synonyms[_return] = variable
            return False
        if len(list(_return.activation.variables)) == 1:
            # Just return. Maybe c_call
            variable.value = _return.value
            self.synonyms[_return] = variable
            return False
        ndepth = depth + 1
        if ndepth > self.max_depth:
            # max depth
            variable.value = _return.value
            self.synonyms[_return] = variable
            return False
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

        if any([any(_return.dependencies_as_source),
                any(variable.dependencies_as_target)]):

            self._add_variable(_return, ndepth, VAR_SCHEMA)
            self.synonyms[variable] = _return

        self._export_activation(new_activation, ndepth)
        self._prepare_rank(new_activation, ndepth)
        result.append("    " * depth + "}")
        return True

    def _export_activation(self, activation, depth=1):
        for variable in activation.variables:
            if (variable.type == "call" and
                    self._add_call(variable, depth)):
                continue

            config = TYPES.get(variable.type)
            if config:
                self._add_variable(variable, depth, config)


        

    def _prepare_rank(self, activation, depth):
        if self.rank_line:
            result = self.result
            created = self.created
            by_line = defaultdict(list)
            for variable in activation.variables:
                if variable in created:
                    by_line[variable.line].append(variable)

            for line, variables in viewitems(by_line):
                result.append("    " * depth + "{rank=same " +
                    " ".join(variable_id(var) for var in variables) + "}")

    def _create_dependencies(self):
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
            if "box--" in target.type:
                typ = "dashed"
            if source != target and osource.type != "arg":
                departing_arrows[source][target] = typ
                arriving_arrows[target][source] = typ

    def _fix_dependencies(self):
        created = self.created
        synonyms = self.synonyms
        arriving_arrows = self.arriving_arrows
        departing_arrows = self.departing_arrows

        removed = (set(viewvalues(self.variables))
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
        result = self.result
        created = self.created
        departing_arrows = self.departing_arrows

        self._fix_dependencies()

        for source, targets in viewitems(departing_arrows):
            if not source in created:
                continue
            dep_act_id = source.activation_id
            dep_act_id = "global" if dep_act_id == -1 else dep_act_id
            for target, style in viewitems(targets):
                if not target in created or source == target:
                    continue
                sup_act_id = target.activation_id
                sup_act_id = "global" if sup_act_id == -1 else sup_act_id

                result.append(('    {} -> {} [style="{}"];').format(
                    variable_id(source), variable_id(target), style
                ))

    def erase(self):
        """Erase graph"""
        self.result = []
        self.created = set()
        self.synonyms = {}
        self.departing_arrows = defaultdict(dict)
        self.arriving_arrows = defaultdict(dict)


    def _export_text(self):
        self.erase()
        result = self.result
        result.append("digraph dependency {")
        result.append("  rankdir=RL;")
        result.append("  node[fontsize=20]")
        getattr(self, self.mode)()
        result.append("}")
        return result

    def simulation(self):
        """Create simulation graph"""
        synonyms = self.synonyms
        variables = self.variables
        for activation in self.trial.initial_activations:
            self._export_activation(activation)
            self._prepare_rank(activation, 1)


        arg_orginal = Variable.fast_arg_and_original(self.trial.id)
        for arg_id, original_id in arg_orginal:
            synonyms[variables[arg_id]] = variables[original_id]

        self._create_dependencies()
        self._show_dependencies()


    def export_text(self):
        """Export facts from trial as text"""
        return "\n".join(self._export_text())

    def _repr_png_(self):
        ipython = get_ipython()
        return ipython.run_cell_magic('dot', '', self.export_text())
