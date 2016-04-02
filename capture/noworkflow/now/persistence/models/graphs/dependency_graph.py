# Copyright (c) 2016 Universidade Federal Fluminense (UFF)
# Copyright (c) 2016 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""Dependency Filter"""

from __future__ import (absolute_import, print_function,
                        division, unicode_literals)

import weakref

from collections import defaultdict

from future.utils import viewitems, viewkeys, viewvalues

from .. import Activation, Variable, VariableDependency, FileAccess
from .. import UniqueFileAccess


class ActivationCluster(object):
    """Represent an activation cluster"""
    def __init__(self, aid, name, depth=1):
        self.components = []
        self.name = name
        self.same_rank = []
        self.depth = depth
        self.activation_id = aid


def variable_id(variable):
    """Return variable identification for .dot file"""
    if isinstance(variable, FileAccess):
        return "a_{}".format(variable.id)
    act_id = variable.activation_id
    act_id = "global" if act_id == -1 else act_id
    return "v_{}_{}".format(act_id, variable.id)


class DependencyConfig(object):                                                  # pylint: disable=too-many-instance-attributes
    """Configure dependency graph"""

    def __init__(self):
        self.show_blackbox_dependencies = False
        self.rank_line = True
        self.show_accesses = True
        self.combine_accesses = True
        self.show_external_files = False
        self.max_depth = float("inf")
        self.show_internal_use = True
        self.mode = "simulation"

    @classmethod
    def create_arguments(cls, add_arg):
        """Create arguments

        Arguments:
        add_arg -- add argument function
        """
        add_arg("-a", "--accesses", type=int, default=1, metavar="A",
                help="R|show file accesses (default: 1)\n"
                     "0 hides file accesses\n"
                     "1 shows each file once (hide external accesses)\n"
                     "2 shows each file once (show external accesses)\n"
                     "3 shows all accesses (except external accesses)\n"
                     "4 shows all accesses (including external accesses)")
        add_arg("-d", "--depth", type=int, default=0, metavar="D",
                help="R|visualization depth (default: 0)\n"
                     "0 represents infinity")
        add_arg("-i", "--show-internal-use", action="store_false",
                help="show variables and functions which name starts with a "
                     "leading underscore")
        add_arg("-l", "--rank-line", action="store_true",
                help="R|align variables of a line in the same column\n"
                     "With this option, all variables in a loop appear\n"
                     "grouped, reducing the width of the graph.\n"
                     "It may affect the graph legibility.\n"
                     "The alignment is independent for each activation.\n")
        add_arg("-m", "--mode", type=str, default="prospective",
                choices=["simulation", "prospective", "dependency"],
                help="R|Graph mode (default: prospective)\n"
                     "'simulation' presents a dataflow graph with all\n"
                     "relevant variables.\n"
                     "'prospective' presents only parameters, calls, and\n"
                     "assignments to calls.\n"
                     "'dependency' presents all dependencies, and ignores\n"
                     "depth, rank-line, and hide-accesses configurations")
        add_arg("-b", "--black-box", action="store_true",
                help="R|propagate black-box dependencies. \n"
                     "Use this option to avoid false negatives. \n"
                     "It shows all dependencies between calls that we do\n"
                     "do not have definitions and that could change some \n"
                     "program state, creating an implicit dependency")


    def read_args(self, args):
        """Read config from args"""
        self.show_accesses = bool(args.accesses)
        self.combine_accesses = args.accesses in {1, 2}
        self.show_external_files = args.accesses in {2, 4}
        self.max_depth = args.depth or float("inf")
        self.show_internal_use = not bool(args.show_internal_use)
        self.rank_line = bool(args.rank_line)
        self.mode = args.mode
        self.show_blackbox_dependencies = bool(args.black_box)


class DependencyFilter(object):                                                  # pylint: disable=too-many-instance-attributes
    """Handle Dot export"""

    def __init__(self, trial):
        super(DependencyFilter, self).__init__()
        self.trial = weakref.proxy(trial)
        self.config = self.trial.dependency_config

        self.valid_types = {"call", "normal", "virtual", "param"}
        self.created = set()
        self.synonyms = {}
        self.departing_arrows = {}
        self.arriving_arrows = {}
        self.variables = {}
        self.accesses = {}

        self.main_cluster = None
        self.current_cluster = None
        self.filtered_variables = set()
        self.dependencies = {}

    def _add_variable(self, variable, cluster=None):
        """Create variable in cluster

        Arguments:
        variable -- Variable
        cluster -- activation cluster
        """
        if cluster is None:
            cluster = self.current_cluster
        if variable.name.startswith("_") and not self.config.show_internal_use:
            return
        self.filtered_variables.add(variable_id(variable))
        cluster.components.append(variable)
        self.created.add(variable)

    def _add_all_variables(self, variables, cluster=None):
        """Create all variables"""
        created = self.created
        synonyms = self.synonyms

        for variable in variables:
            variable = synonyms.get(variable, variable)
            if not variable in created and variable.type in self.valid_types:
                self._add_variable(variable, cluster)

    def _all_accesses(self, activation, depth):
        """Get all file accesses recursively if it reaches the maximum depth"""
        for access in activation.file_accesses:
            if self.config.show_external_files or access.is_internal:
                yield access
        if depth + 1 > self.config.max_depth:
            for act in activation.children:
                for access in self._all_accesses(act, depth + 1):
                    yield access

    def _add_call(self, variable, cluster, recursive_function):
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
        accesses = self.accesses
        return_ = variable.return_dependency
        if not return_:
            # Fake call
            return None, "fake"
        activation_id = variable.activation_id
        new_activation_id = return_.activation_id
        if self.config.show_accesses:
            for access in self._all_accesses(return_.activation, cluster.depth):
                access = UniqueFileAccess(access._alchemy_pk)
                if (not self.config.combine_accesses or
                        access.name not in accesses):
                    access.value = ""
                    access.line = ""
                    accesses[access.name] = access
                    fcluster = self.main_cluster
                    if not access.is_internal:
                        fcluster = cluster

                    self._add_variable(access, fcluster)
                else:
                    access = accesses[access.name]
                if set("r+") & set(access.mode):
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
        if cluster.depth + 1 > self.config.max_depth:
            # max depth
            variable.value = return_.value
            self.synonyms[return_] = variable
            return None, "max_depth"
        trial_id = variable.trial_id
        new_activation = Activation((trial_id, new_activation_id))
        ncluster = self.current_cluster = ActivationCluster(
            new_activation_id, variable.name, cluster.depth + 1
        )
        cluster.components.append(ncluster)

        if any([any(return_.dependencies_as_source),
                any(variable.dependencies_as_target)]):

            self._add_variable(return_, ncluster)
            self.synonyms[variable] = return_

        self._add_all_variables(new_activation.param_variables, ncluster)

        recursive_function(new_activation, ncluster)
        self._prepare_rank(new_activation, ncluster)
        return return_, "subgraph"

    def _prepare_rank(self, activation, cluster):
        """Group variables by line"""
        if self.config.rank_line:
            created = self.created
            by_line = defaultdict(list)
            for variable in activation.variables:
                if variable in created:
                    by_line[variable.line].append(variable)

            for variables in viewvalues(by_line):
                cluster.same_rank.append(variables)

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
                    not self.config.show_blackbox_dependencies):
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
                        not self.config.show_blackbox_dependencies):
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
                        not self.config.show_blackbox_dependencies):
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
        created = self.created
        departing_arrows = self.departing_arrows

        self._fix_dependencies()

        for source, targets in viewitems(departing_arrows):
            if source not in created:
                continue
            for target, style in viewitems(targets):
                if target not in created or source == target:
                    continue
                dep = (variable_id(source), variable_id(target))
                self.dependencies[dep] = style

    def _dataflow(self, function):
        """Create dataflow graph"""
        synonyms = self.synonyms
        variables = self.variables
        for activation in self.trial.initial_activations:
            function(activation, self.main_cluster)
            self._prepare_rank(activation, self.main_cluster)

        arg_orginal = Variable.fast_arg_and_original(self.trial.id)
        for arg_id, original_id in arg_orginal:
            synonyms[variables[arg_id]] = variables[original_id]
            if variables[original_id].type == "arg":
                synonyms[variables[arg_id]] = synonyms[variables[original_id]]

        self._create_dependencies()
        self._show_dependencies()

    def _simulation_activation(self, activation, cluster):
        """Export simulation activation"""
        for variable in activation.variables:
            if (variable.type == "call" and
                    self._add_call(variable, cluster,
                                   self._simulation_activation)[0]):
                continue
            if variable.type in self.valid_types:
                self._add_variable(variable, cluster)

    def _prospective_activation(self, activation, cluster):
        """Export prospective activation"""
        # ToDo: param dependencies
        for variable in activation.no_param_variables:
            if variable.type == "call":
                return_, mode = self._add_call(variable, cluster,
                                               self._prospective_activation)
                if not return_:
                    self._add_variable(variable, cluster)

                if mode == "fake":
                    box = variable.box_dependency
                    if not box:
                        box = variable
                    self._add_all_variables(box.dependencies, cluster)

                elif mode in ("c_call", "just_return"):
                    return_ = variable.return_dependency
                    box = return_.box_dependency
                    if box:
                        self._add_all_variables(box.dependencies, cluster)

                elif mode == "max_depth":
                    return_ = variable.return_dependency
                    for var in return_.activation.param_variables:
                        self._add_all_variables(var.dependencies, cluster)
                elif mode == "subgraph":
                    for var in return_.activation.param_variables:
                        self._add_all_variables(var.dependencies, cluster)

                self._add_all_variables(variable.dependents, cluster)

    def simulation(self):
        """Create simulation graph"""
        self._dataflow(self._simulation_activation)

    def prospective(self):
        """Create prospective graph"""
        self._dataflow(self._prospective_activation)

    def dependency(self):
        """Create dependency graph"""
        self.valid_types = {
            "call", "normal", "virtual", "param", "import",
            "--blackbox--", "--graybox--"
        }

        for variable in viewvalues(self.variables):
            self._add_variable(variable, self.main_cluster)

        self._create_dependencies(skip_arg=False)
        self._show_dependencies()

    def erase(self):
        """Erase graph"""
        self.valid_types = {"call", "normal", "virtual", "param"}
        self.created = set()
        self.synonyms = {}
        self.departing_arrows = defaultdict(dict)
        self.arriving_arrows = defaultdict(dict)
        self.variables = {v.id: v for v in self.trial.variables}
        self.accesses = {}

        self.main_cluster = ActivationCluster(-1, "main")
        self.current_cluster = self.main_cluster
        self.filtered_variables = set()
        self.dependencies = {}

    def run(self):
        """Filter variables graph according to mode"""
        self.erase()
        getattr(self, self.config.mode)()
