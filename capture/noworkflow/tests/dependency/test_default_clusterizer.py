# Copyright (c) 2017 Universidade Federal Fluminense (UFF)
# Copyright (c) 2017 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""Test dataflow clusterizer"""
from __future__ import (absolute_import, print_function,
                        division, unicode_literals)

from future.utils import viewitems

from ...now.persistence.models import Trial
from ...now.models.dependency_graph.synonymers import Synonymer
from ...now.models.dependency_graph.synonymers import SameSynonymer
from ...now.models.dependency_graph.synonymers import ReferenceSynonymer
from ...now.models.dependency_graph.synonymers import AccessNameSynonymer
from ...now.models.dependency_graph.synonymers import JoinedSynonymer
from ...now.models.dependency_graph.filters import AcceptAllNodesFilter
from ...now.models.dependency_graph.filters import FilterAccessesOut
from ...now.models.dependency_graph.filters import FilterTypesOut
from ...now.models.dependency_graph.filters import JoinedFilter
from ...now.models.dependency_graph.attributes import EMPTY_ATTR, ACCESS_ATTR
from ...now.models.dependency_graph.attributes import PROPAGATED_ATTR
from ...now.models.dependency_graph.attributes import REFERENCE_ATTR
from ...now.models.dependency_graph.clusterizer import Clusterizer
from ...now.models.dependency_graph.node_types import EvaluationNode

from ..collection_testcase import CollectionTestCase, cluster


class TestClusterizer(CollectionTestCase):
    """Test Dataflow Clusterizer"""
    # pylint: disable=missing-docstring
    # pylint: disable=invalid-name
    # pylint: disable=too-many-public-methods

    def test_no_evaluations(self):
        self.script("# script.py\n"
                    "\n")
        self.clean_execution()

        script = self.evaluation_node(name="script.py")

        trial = Trial()
        clusterizer = Clusterizer(trial, synonymer=Synonymer()).run()

        self.assertEqual(
            (script, cluster(script), []),
            clusterizer.main_cluster.to_tree()
        )
        self.assertEqual({}, clusterizer.dependencies)

    def test_single_evaluation(self):
        self.script("# script.py\n"
                    "1\n")
        self.clean_execution()

        script = self.evaluation_node(name="script.py")
        num1 = self.evaluation_node(name="1")

        trial = Trial()
        clusterizer = Clusterizer(trial, synonymer=Synonymer()).run()

        self.assertEqual(
            (script, cluster(script), [num1]),
            clusterizer.main_cluster.to_tree()
        )
        self.assertEqual({}, clusterizer.dependencies)

    def test_two_independent_evaluations(self):
        self.script("# script.py\n"
                    "1\n"
                    "2\n")
        self.clean_execution()

        script = self.evaluation_node(name="script.py")
        num1 = self.evaluation_node(name="1")
        num2 = self.evaluation_node(name="2")

        trial = Trial()
        clusterizer = Clusterizer(trial, synonymer=Synonymer()).run()

        self.assertEqual(
            (script, cluster(script), [num1, num2]),
            clusterizer.main_cluster.to_tree()
        )
        self.assertEqual({}, clusterizer.dependencies)

    def test_two_dependent_evaluations(self):
        self.script("# script.py\n"
                    "a = 1\n")
        self.clean_execution()

        script = self.evaluation_node(name="script.py")
        num1 = self.evaluation_node(name="1")
        vara = self.evaluation_node(name="a")

        trial = Trial()
        clusterizer = Clusterizer(trial, synonymer=Synonymer()).run()

        self.assertEqual(
            (script, cluster(script), [num1, vara]),
            clusterizer.main_cluster.to_tree()
        )
        created = clusterizer.created
        self.assertEqual([
            ((created[vara][1], created[num1][1]), {REFERENCE_ATTR}),
        ], sorted([item for item in viewitems(clusterizer.dependencies)]))

    def test_chain_of_evaluations(self):
        self.script("# script.py\n"
                    "a = 1\n"
                    "b = a\n"
                    "c = b\n")
        self.clean_execution()

        script = self.evaluation_node(name="script.py")
        num1 = self.evaluation_node(name="1")
        vara_w = self.evaluation_node(name="a", mode="w")
        vara_r = self.evaluation_node(name="a", mode="r")
        varb_w = self.evaluation_node(name="b", mode="w")
        varb_r = self.evaluation_node(name="b", mode="r")
        varc_w = self.evaluation_node(name="c", mode="w")

        trial = Trial()
        clusterizer = Clusterizer(trial, synonymer=Synonymer()).run()

        self.assertEqual(
            (script, cluster(script), [
                num1, vara_w, vara_r, varb_w, varb_r, varc_w
            ]),
            clusterizer.main_cluster.to_tree()
        )
        created = clusterizer.created
        self.assertEqual([
            ((created[vara_w][1], created[num1][1]), {REFERENCE_ATTR}),
            ((created[vara_r][1], created[vara_w][1]), {REFERENCE_ATTR}),
            ((created[varb_w][1], created[vara_r][1]), {REFERENCE_ATTR}),
            ((created[varb_r][1], created[varb_w][1]), {REFERENCE_ATTR}),
            ((created[varc_w][1], created[varb_r][1]), {REFERENCE_ATTR}),
        ], sorted([item for item in viewitems(clusterizer.dependencies)]))

    def test_chain_of_evaluations_with_custom_filter(self):
        self.script("# script.py\n"
                    "a = 1\n"
                    "b = a\n"
                    "c = b\n")
        self.clean_execution()

        script = self.evaluation_node(name="script.py")
        vara_w = self.evaluation_node(name="a", mode="w")
        vara_r = self.evaluation_node(name="a", mode="r")
        varc_w = self.evaluation_node(name="c", mode="w")

        trial = Trial()
        clusterizer = Clusterizer(trial, synonymer=Synonymer())
        class CustomFilter(AcceptAllNodesFilter):
            def __contains__(self, node):
                if isinstance(node, EvaluationNode):
                    return node.evaluation.code_component.name in ("a", "c")
                return super(CustomFilter, self).__contains__(node)
        clusterizer.replace_filter = CustomFilter()
        clusterizer.run()

        self.assertEqual(
            (script, cluster(script), [vara_w, vara_r, varc_w]),
            clusterizer.main_cluster.to_tree()
        )
        created = clusterizer.created
        self.assertEqual([
            ((created[vara_r][1], created[vara_w][1]), {REFERENCE_ATTR}),
            ((created[varc_w][1], created[vara_r][1]), 
                {REFERENCE_ATTR, PROPAGATED_ATTR}),
        ], sorted([item for item in viewitems(clusterizer.dependencies)]))
        from ...now.models.dependency_graph.prov_visitor import ProvVisitor
        visitor = ProvVisitor(clusterizer, create_activities=True)
        visitor.visit(clusterizer)
        prov = "\n".join(visitor.result)
        with open("/home/joao/vprov.provn", "w") as f:
            f.write(prov)

    def test_chain_of_evaluations_with_same_assignment_synonymer(self):
        self.script("# script.py\n"
                    "a = 1\n"
                    "b = a\n"
                    "c = b\n")
        self.clean_execution()

        script = self.evaluation_node(name="script.py")
        num1 = self.evaluation_node(name="1")
        vara_w = self.evaluation_node(name="a", mode="w")
        varb_w = self.evaluation_node(name="b", mode="w")
        varc_w = self.evaluation_node(name="c", mode="w")

        trial = Trial()
        clusterizer = Clusterizer(trial)
        clusterizer.replace_synonymer = SameSynonymer()
        clusterizer.run()

        self.assertEqual(
            (script, cluster(script), [num1, vara_w, varb_w, varc_w]),
            clusterizer.main_cluster.to_tree()
        )
        created = clusterizer.created
        self.assertEqual([
            ((created[vara_w][1], created[num1][1]), {REFERENCE_ATTR}),
            ((created[varb_w][1], created[vara_w][1]), {REFERENCE_ATTR}),
            ((created[varc_w][1], created[varb_w][1]), {REFERENCE_ATTR}),
        ], sorted([item for item in viewitems(clusterizer.dependencies)]))

    def test_chain_of_evaluations_with_same_value_synonymer(self):
        self.script("# script.py\n"
                    "a = 1\n"
                    "b = a\n"
                    "c = b\n")
        self.clean_execution()

        script = self.evaluation_node(name="script.py")
        num1 = self.evaluation_node(name="1")

        trial = Trial()
        clusterizer = Clusterizer(trial)
        clusterizer.replace_synonymer = ReferenceSynonymer()
        clusterizer.run()

        self.assertEqual(
            (script, cluster(script), [num1]),
            clusterizer.main_cluster.to_tree()
        )
        self.assertEqual({}, clusterizer.dependencies)

    def test_single_evaluation_with_values(self):
        self.script("# script.py\n"
                    "1\n")
        self.clean_execution()

        script = self.evaluation_node(name="script.py")
        num1 = self.evaluation_node(name="1")
        var_int = self.evaluation_node(name=self.rtype('int'))
        var_type = self.evaluation_node(name=self.rtype('type'))

        trial = Trial()
        clusterizer = Clusterizer(trial, synonymer=Synonymer())
        clusterizer.replace_filter = AcceptAllNodesFilter()
        clusterizer.run()

        self.assertEqual(
            (script, cluster(script), [num1, var_int, var_type]),
            clusterizer.main_cluster.to_tree()
        )
        created = clusterizer.created
        class_attr = EMPTY_ATTR.update({"label": ".__class__"})
        self.assertEqual([
            ((created[num1][1], created[var_int][1]), {class_attr}),
            ((created[var_int][1], created[var_type][1]), {class_attr}),
        ], sorted([item for item in viewitems(clusterizer.dependencies)]))

    def test_evaluation_with_members(self):
        self.script("# script.py\n"
                    "[1]\n")
        self.clean_execution()
        trial = Trial()
        clusterizer = Clusterizer(trial, synonymer=Synonymer())
        clusterizer.replace_filter = AcceptAllNodesFilter()
        clusterizer.run()

        script = self.evaluation_node(name="script.py")
        var_list = self.evaluation_node(name="[1]")
        var_num = self.evaluation_node(name="1")
        var_list_type = self.evaluation_node(name=self.rtype('list'))
        var_int = self.evaluation_node(name=self.rtype('int'))
        var_type = self.evaluation_node(name=self.rtype('type'))

        self.assertEqual(
            (script, cluster(script), [
                var_num, var_int, var_type,
                var_list, var_list_type,
            ]),
            clusterizer.main_cluster.to_tree()
        )
        created = clusterizer.created
        class_attr = EMPTY_ATTR.update({"label": ".__class__"})
        self.assertEqual([
            ((created[var_num][1], created[var_int][1]), {class_attr}),
            ((created[var_int][1], created[var_type][1]), {class_attr}),
            ((created[var_list][1], created[var_num][1]),
                {EMPTY_ATTR.update({"label": "[0]"}), EMPTY_ATTR}),
            ((created[var_list][1], created[var_list_type][1]), {class_attr}),
            ((created[var_list_type][1], created[var_type][1]), {class_attr}),
        ], sorted([item for item in viewitems(clusterizer.dependencies)]))

    def test_single_activation(self):
        self.script("# script.py\n"
                    "int()\n")
        self.clean_execution()

        script = self.evaluation_node(name="script.py")
        var_act = self.evaluation_node(name="int()")
        var_int = self.evaluation_node(name="int")

        trial = Trial()
        clusterizer = Clusterizer(trial, synonymer=Synonymer()).run()

        self.assertEqual(
            (script, cluster(script), [var_int, var_act]),
            clusterizer.main_cluster.to_tree()
        )
        created = clusterizer.created
        self.assertEqual([
            ((created[var_act][1], created[var_int][1]), {EMPTY_ATTR}),
        ], sorted([item for item in viewitems(clusterizer.dependencies)]))

    def test_single_activation_dependencies(self):
        self.script("# script.py\n"
                    "x = int('1')\n")
        self.clean_execution()

        script = self.evaluation_node(name="script.py")
        var_act = self.evaluation_node(name="int('1')")
        var_int = self.evaluation_node(name="int")
        var_param = self.evaluation_node(name="'1'")
        var_x = self.evaluation_node(name="x")

        trial = Trial()
        clusterizer = Clusterizer(trial, synonymer=Synonymer()).run()

        self.assertEqual(
            (script, cluster(script), [var_int, var_act, var_param, var_x]),
            clusterizer.main_cluster.to_tree()
        )
        created = clusterizer.created
        self.assertEqual([
            ((created[var_act][1], created[var_int][1]), {EMPTY_ATTR}),
            ((created[var_act][1], created[var_param][1]), {EMPTY_ATTR}),
            ((created[var_x][1], created[var_act][1]), {REFERENCE_ATTR}),
        ], sorted([item for item in viewitems(clusterizer.dependencies)]))

    def test_user_activation_max_depth_1(self):
        self.script("# script.py\n"
                    "def f(x):\n"
                    "    return x\n"
                    "y = f('1')\n")
        self.clean_execution()

        write_f_eval = self.evaluation_node(name="f", mode="w")
        read_f_eval = self.evaluation_node(name="f", mode="r")
        script = self.evaluation_node(name="script.py")
        var_act = self.evaluation_node(name="f('1')")
        var_param = self.evaluation_node(name="'1'")
        var_y = self.evaluation_node(name="y")

        trial = Trial()
        clusterizer = Clusterizer(trial, synonymer=Synonymer())
        clusterizer.config.max_depth = 1
        clusterizer.run()

        self.assertEqual(
            (script, cluster(script),
                [write_f_eval, read_f_eval, var_act, var_param, var_y]),
            clusterizer.main_cluster.to_tree()
        )
        created = clusterizer.created
        self.assertEqual(sorted([
            ((created[read_f_eval][1], created[write_f_eval][1]), {REFERENCE_ATTR}),
            ((created[var_act][1], created[read_f_eval][1]), {EMPTY_ATTR}),
            ((created[var_y][1], created[var_act][1]), {REFERENCE_ATTR}),
            ((created[var_act][1], created[var_param][1]), {REFERENCE_ATTR, PROPAGATED_ATTR}),
        ]), sorted([item for item in viewitems(clusterizer.dependencies)]))

    def test_user_activation_no_max_depth(self):
        self.script("# script.py\n"
                    "def f(x):\n"
                    "    return x\n"
                    "y = f('1')\n")
        self.clean_execution()

        write_f_eval = self.evaluation_node(name="f", mode="w")
        read_f_eval = self.evaluation_node(name="f", mode="r")
        script = self.evaluation_node(name="script.py")
        var_act = self.evaluation_node(name="f('1')")
        var_param = self.evaluation_node(name="'1'")
        var_y = self.evaluation_node(name="y")
        var_x_w = self.evaluation_node(name="x", mode="w")
        var_x_r = self.evaluation_node(name="x", mode="r")

        trial = Trial()
        clusterizer = Clusterizer(trial, synonymer=Synonymer())
        clusterizer.run()

        self.assertEqual(
            (script, cluster(script), [
                write_f_eval, read_f_eval,
                (var_act, cluster(var_act), [var_x_w, var_x_r]),
                var_param, var_y
            ]),
            clusterizer.main_cluster.to_tree()
        )
        created = clusterizer.created
        self.assertEqual(sorted([
            ((created[read_f_eval][1], created[write_f_eval][1]), {REFERENCE_ATTR}),
            ((created[var_act][1], created[read_f_eval][1]), {EMPTY_ATTR}),
            ((created[var_y][1], created[var_act][1]), {REFERENCE_ATTR}),
            ((created[var_act][1], created[var_x_r][1]), {REFERENCE_ATTR}),
            ((created[var_x_w][1], created[var_param][1]), {REFERENCE_ATTR}),
            ((created[var_x_r][1], created[var_x_w][1]), {REFERENCE_ATTR}),
        ]), sorted([item for item in viewitems(clusterizer.dependencies)]))

    def test_file_accesses(self):
        self.script("# script.py\n"
                    "def f(x):\n"
                    "    return g(x)\n"
                    "def g(x):\n"
                    "    return x\n"
                    "y = f('1')\n")
        self.clean_execution()

        write_f_eval = self.evaluation_node(name="f", mode="w")
        write_g_eval = self.evaluation_node(name="g", mode="w")
        read_f_eval = self.evaluation_node(name="f", mode="r")
        read_g_eval = self.evaluation_node(name="g", mode="r")
        script = self.evaluation_node(name="script.py")
        var_act_f = self.evaluation_node(name="f('1')")
        var_act_g = self.evaluation_node(name="g(x)")
        var_param = self.evaluation_node(name="'1'")
        var_y = self.evaluation_node(name="y")
        var_fx_w = self.evaluation_node(name="x", mode="w", first_char_line=2)
        var_fx_r = self.evaluation_node(name="x", mode="r", first_char_line=3)
        var_gx_w = self.evaluation_node(name="x", mode="w", first_char_line=4)
        var_gx_r = self.evaluation_node(name="x", mode="r", first_char_line=5)

        fas = self.metascript.file_accesses_store
        acc1 = fas.add_object(1, "teste", self.metascript.get_time())
        acc1.mode = "w"
        acc1.activation_id = int(var_act_f.split("_")[-1])
        acc2 = fas.add_object(1, "teste2", self.metascript.get_time())
        acc2.mode = "r"
        acc2.activation_id = int(var_act_g.split("_")[-1])
        fas.do_store()
        trial = Trial()

        var_acc1 = "a_{}".format(acc1.id)
        var_acc2 = "a_{}".format(acc2.id)

        clusterizer = Clusterizer(trial, synonymer=Synonymer())
        clusterizer.run()

        self.assertEqual(
            (script, cluster(script), [
                write_f_eval, write_g_eval, read_f_eval,
                (var_act_f, cluster(var_act_f), [
                    var_fx_w, read_g_eval,
                    (var_act_g, cluster(var_act_g), [
                        var_gx_w, var_gx_r,
                    ]),
                    var_acc2, var_fx_r
                ]),
                var_acc1, var_param, var_y
            ]),
            clusterizer.main_cluster.to_tree()
        )
        created = clusterizer.created
        self.assertEqual(sorted([
            ((created[read_g_eval][1], created[write_g_eval][1]), {REFERENCE_ATTR}),
            ((created[read_f_eval][1], created[write_f_eval][1]), {REFERENCE_ATTR}),
            ((created[var_act_f][1], created[read_f_eval][1]), {EMPTY_ATTR}),
            ((created[var_act_g][1], created[read_g_eval][1]), {EMPTY_ATTR}),
            ((created[var_acc1][1], created[var_act_f][1]), {ACCESS_ATTR}),
            ((created[var_act_g][1], created[var_acc2][1]), {ACCESS_ATTR}),
            ((created[var_act_g][1], created[var_gx_r][1]), {REFERENCE_ATTR}),
            ((created[var_fx_r][1], created[var_fx_w][1]), {REFERENCE_ATTR}),
            ((created[var_gx_w][1], created[var_fx_r][1]), {REFERENCE_ATTR}),
            ((created[var_gx_r][1], created[var_gx_w][1]), {REFERENCE_ATTR}),
            ((created[var_y][1], created[var_act_f][1]), {REFERENCE_ATTR}),
            ((created[var_act_f][1], created[var_act_g][1]), {REFERENCE_ATTR}),
            ((created[var_fx_w][1], created[var_param][1]), {REFERENCE_ATTR}),
        ]), sorted([item for item in viewitems(clusterizer.dependencies)]))

    def test_file_accesses_max_depth_2(self):
        self.script("# script.py\n"
                    "def f(x):\n"
                    "    return g(x)\n"
                    "def g(x):\n"
                    "    return x\n"
                    "y = f('1')\n")
        self.clean_execution()

        write_f_eval = self.evaluation_node(name="f", mode="w")
        write_g_eval = self.evaluation_node(name="g", mode="w")
        read_f_eval = self.evaluation_node(name="f", mode="r")
        read_g_eval = self.evaluation_node(name="g", mode="r")
        script = self.evaluation_node(name="script.py")
        var_act_f = self.evaluation_node(name="f('1')")
        var_act_g = self.evaluation_node(name="g(x)")
        var_param = self.evaluation_node(name="'1'")
        var_y = self.evaluation_node(name="y")
        var_fx_w = self.evaluation_node(name="x", mode="w", first_char_line=2)
        var_fx_r = self.evaluation_node(name="x", mode="r", first_char_line=3)

        fas = self.metascript.file_accesses_store
        acc1 = fas.add_object(1, "teste", self.metascript.get_time())
        acc1.mode = "w"
        acc1.activation_id = int(var_act_f.split("_")[-1])
        acc2 = fas.add_object(1, "teste2", self.metascript.get_time())
        acc2.mode = "r"
        acc2.activation_id = int(var_act_g.split("_")[-1])
        fas.do_store()
        trial = Trial()

        var_acc1 = "a_{}".format(acc1.id)
        var_acc2 = "a_{}".format(acc2.id)

        clusterizer = Clusterizer(trial, synonymer=Synonymer())
        clusterizer.config.max_depth = 2
        clusterizer.run()

        self.assertEqual(
            (script, cluster(script), [
                write_f_eval, write_g_eval, read_f_eval,
                (var_act_f, cluster(var_act_f), [
                    var_fx_w, read_g_eval, var_act_g, 
                    var_acc2, var_fx_r
                ]),
                var_acc1, var_param, var_y
            ]),
            clusterizer.main_cluster.to_tree()
        )
        created = clusterizer.created
        self.assertEqual(sorted([
            ((created[read_g_eval][1], created[write_g_eval][1]), {REFERENCE_ATTR}),
            ((created[read_f_eval][1], created[write_f_eval][1]), {REFERENCE_ATTR}),
            ((created[var_act_f][1], created[read_f_eval][1]), {EMPTY_ATTR}),
            ((created[var_act_g][1], created[read_g_eval][1]), {EMPTY_ATTR}),
            ((created[var_acc1][1], created[var_act_f][1]), {ACCESS_ATTR}),
            ((created[var_act_g][1], created[var_acc2][1]), {ACCESS_ATTR}),
            ((created[var_act_g][1], created[var_fx_r][1]),
                {REFERENCE_ATTR, PROPAGATED_ATTR}),
            ((created[var_fx_r][1], created[var_fx_w][1]), {REFERENCE_ATTR}),
            ((created[var_y][1], created[var_act_f][1]), {REFERENCE_ATTR}),
            ((created[var_act_f][1], created[var_act_g][1]), {REFERENCE_ATTR}),
            ((created[var_fx_w][1], created[var_param][1]), {REFERENCE_ATTR}),
        ]), sorted([item for item in viewitems(clusterizer.dependencies)]))

    def test_file_accesses_max_depth_1(self):
        self.script("# script.py\n"
                    "def f(x):\n"
                    "    return g(x)\n"
                    "def g(x):\n"
                    "    return x\n"
                    "y = f('1')\n")
        self.clean_execution()

        write_f_eval = self.evaluation_node(name="f", mode="w")
        write_g_eval = self.evaluation_node(name="g", mode="w")
        read_f_eval = self.evaluation_node(name="f", mode="r")
        script = self.evaluation_node(name="script.py")
        var_act_f = self.evaluation_node(name="f('1')")
        var_act_g = self.evaluation_node(name="g(x)")
        var_param = self.evaluation_node(name="'1'")
        var_y = self.evaluation_node(name="y")

        fas = self.metascript.file_accesses_store
        acc1 = fas.add_object(1, "teste", self.metascript.get_time())
        acc1.mode = "w"
        acc1.activation_id = int(var_act_f.split("_")[-1])
        acc2 = fas.add_object(1, "teste2", self.metascript.get_time())
        acc2.mode = "r"
        acc2.activation_id = int(var_act_g.split("_")[-1])
        fas.do_store()
        trial = Trial()

        var_acc1 = "a_{}".format(acc1.id)
        var_acc2 = "a_{}".format(acc2.id)

        clusterizer = Clusterizer(trial, synonymer=Synonymer())
        clusterizer.config.max_depth = 1
        clusterizer.run()

        self.assertEqual(
            (script, cluster(script), [
                write_f_eval, write_g_eval, read_f_eval, var_act_f,
                var_acc1, var_acc2, var_param, var_y
            ]),
            clusterizer.main_cluster.to_tree()
        )
        created = clusterizer.created
        self.assertEqual(sorted([
            ((created[read_f_eval][1], created[write_f_eval][1]), {REFERENCE_ATTR}),
            ((created[var_act_f][1], created[read_f_eval][1]), {EMPTY_ATTR}),
            ((created[var_act_f][1], created[write_g_eval][1]), 
                {EMPTY_ATTR, REFERENCE_ATTR, PROPAGATED_ATTR}),
            ((created[var_acc1][1], created[var_act_f][1]), {ACCESS_ATTR}),
            ((created[var_y][1], created[var_act_f][1]), {REFERENCE_ATTR}),
            ((created[var_act_f][1], created[var_acc2][1]),
                {ACCESS_ATTR, PROPAGATED_ATTR}),
            ((created[var_act_f][1], created[var_param][1]),
                {REFERENCE_ATTR, PROPAGATED_ATTR}),
        ]), sorted([item for item in viewitems(clusterizer.dependencies)]))

    def test_file_accesses_separate_accesses(self):
        self.script("# script.py\n"
                    "def f(x):\n"
                    "    return g(x)\n"
                    "def g(x):\n"
                    "    return x\n"
                    "y = f('1')\n")
        self.clean_execution()

        write_f_eval = self.evaluation_node(name="f", mode="w")
        write_g_eval = self.evaluation_node(name="g", mode="w")
        read_f_eval = self.evaluation_node(name="f", mode="r")
        read_g_eval = self.evaluation_node(name="g", mode="r")
        script = self.evaluation_node(name="script.py")
        var_act_f = self.evaluation_node(name="f('1')")
        var_act_g = self.evaluation_node(name="g(x)")
        var_param = self.evaluation_node(name="'1'")
        var_y = self.evaluation_node(name="y")
        var_fx_w = self.evaluation_node(name="x", mode="w", first_char_line=2)
        var_fx_r = self.evaluation_node(name="x", mode="r", first_char_line=3)
        var_gx_w = self.evaluation_node(name="x", mode="w", first_char_line=4)
        var_gx_r = self.evaluation_node(name="x", mode="r", first_char_line=5)

        fas = self.metascript.file_accesses_store
        acc1 = fas.add_object(1, "teste", self.metascript.get_time())
        acc1.mode = "w"
        acc1.activation_id = int(var_act_f.split("_")[-1])
        acc2 = fas.add_object(1, "teste", self.metascript.get_time())
        acc2.mode = "r"
        acc2.activation_id = int(var_act_f.split("_")[-1])
        fas.do_store()
        trial = Trial()

        var_acc1 = "a_{}".format(acc1.id)
        var_acc2 = "a_{}".format(acc2.id)

        clusterizer = Clusterizer(trial, synonymer=Synonymer())
        clusterizer.run()

        self.assertEqual(
            (script, cluster(script), [
                write_f_eval, write_g_eval, read_f_eval,
                (var_act_f, cluster(var_act_f), [
                    var_fx_w, read_g_eval,
                    (var_act_g, cluster(var_act_g), [
                        var_gx_w, var_gx_r,
                    ]),
                    var_fx_r
                ]),
                var_acc1, var_acc2, var_param, var_y
            ]),
            clusterizer.main_cluster.to_tree()
        )
        created = clusterizer.created
        self.assertEqual(sorted([
            ((created[read_g_eval][1], created[write_g_eval][1]), {REFERENCE_ATTR}),
            ((created[read_f_eval][1], created[write_f_eval][1]), {REFERENCE_ATTR}),
            ((created[var_act_f][1], created[read_f_eval][1]), {EMPTY_ATTR}),
            ((created[var_act_g][1], created[read_g_eval][1]), {EMPTY_ATTR}),
            ((created[var_acc1][1], created[var_act_f][1]), {ACCESS_ATTR}),
            ((created[var_act_g][1], created[var_gx_r][1]), {REFERENCE_ATTR}),
            ((created[var_fx_r][1], created[var_fx_w][1]), {REFERENCE_ATTR}),
            ((created[var_gx_w][1], created[var_fx_r][1]), {REFERENCE_ATTR}),
            ((created[var_gx_r][1], created[var_gx_w][1]), {REFERENCE_ATTR}),
            ((created[var_y][1], created[var_act_f][1]), {REFERENCE_ATTR}),
            ((created[var_act_f][1], created[var_acc2][1]), {ACCESS_ATTR}),
            ((created[var_act_f][1], created[var_act_g][1]), {REFERENCE_ATTR}),
            ((created[var_fx_w][1], created[var_param][1]), {REFERENCE_ATTR}),
        ]), sorted([item for item in viewitems(clusterizer.dependencies)]))

    def test_file_accesses_combine_accesses_synonymer(self):
        self.script("# script.py\n"
                    "def f(x):\n"
                    "    return g(x)\n"
                    "def g(x):\n"
                    "    return x\n"
                    "y = f('1')\n")
        self.clean_execution()

        write_f_eval = self.evaluation_node(name="f", mode="w")
        write_g_eval = self.evaluation_node(name="g", mode="w")
        read_f_eval = self.evaluation_node(name="f", mode="r")
        read_g_eval = self.evaluation_node(name="g", mode="r")
        script = self.evaluation_node(name="script.py")
        var_act_f = self.evaluation_node(name="f('1')")
        var_act_g = self.evaluation_node(name="g(x)")
        var_param = self.evaluation_node(name="'1'")
        var_y = self.evaluation_node(name="y")
        var_fx_w = self.evaluation_node(name="x", mode="w", first_char_line=2)
        var_fx_r = self.evaluation_node(name="x", mode="r", first_char_line=3)
        var_gx_w = self.evaluation_node(name="x", mode="w", first_char_line=4)
        var_gx_r = self.evaluation_node(name="x", mode="r", first_char_line=5)

        fas = self.metascript.file_accesses_store
        acc1 = fas.add_object(1, "teste", self.metascript.get_time())
        acc1.mode = "w"
        acc1.activation_id = int(var_act_f.split("_")[-1])
        acc2 = fas.add_object(1, "teste", self.metascript.get_time())
        acc2.mode = "r"
        acc2.activation_id = int(var_act_f.split("_")[-1])
        fas.do_store()
        trial = Trial()

        var_acc1 = "a_{}".format(acc1.id)

        clusterizer = Clusterizer(trial)
        clusterizer.replace_synonymer = AccessNameSynonymer()
        clusterizer.run()

        self.assertEqual(
            (script, cluster(script), [
                write_f_eval, write_g_eval, read_f_eval,
                (var_act_f, cluster(var_act_f), [
                    var_fx_w, read_g_eval,
                    (var_act_g, cluster(var_act_g), [
                        var_gx_w, var_gx_r,
                    ]),
                    var_fx_r
                ]),
                var_acc1, var_param, var_y
            ]),
            clusterizer.main_cluster.to_tree()
        )
        created = clusterizer.created
        self.assertEqual(sorted([
            ((created[read_g_eval][1], created[write_g_eval][1]), {REFERENCE_ATTR}),
            ((created[read_f_eval][1], created[write_f_eval][1]), {REFERENCE_ATTR}),
            ((created[var_act_f][1], created[read_f_eval][1]), {EMPTY_ATTR}),
            ((created[var_act_g][1], created[read_g_eval][1]), {EMPTY_ATTR}),
            ((created[var_acc1][1], created[var_act_f][1]), {ACCESS_ATTR}),
            ((created[var_act_g][1], created[var_gx_r][1]), {REFERENCE_ATTR}),
            ((created[var_fx_r][1], created[var_fx_w][1]), {REFERENCE_ATTR}),
            ((created[var_gx_w][1], created[var_fx_r][1]), {REFERENCE_ATTR}),
            ((created[var_gx_r][1], created[var_gx_w][1]), {REFERENCE_ATTR}),
            ((created[var_y][1], created[var_act_f][1]), {REFERENCE_ATTR}),
            ((created[var_act_f][1], created[var_acc1][1]), {ACCESS_ATTR}),
            ((created[var_act_f][1], created[var_act_g][1]), {REFERENCE_ATTR}),
            ((created[var_fx_w][1], created[var_param][1]), {REFERENCE_ATTR}),
        ]), sorted([item for item in viewitems(clusterizer.dependencies)]))

    def test_file_accesses_joined_synonymer(self):
        self.script("# script.py\n"
                    "def f(x):\n"
                    "    return g(x)\n"
                    "def g(x):\n"
                    "    return x\n"
                    "y = f('1')\n")
        self.clean_execution()

        write_f_eval = self.evaluation_node(name="f", mode="w")
        write_g_eval = self.evaluation_node(name="g", mode="w")
        read_f_eval = self.evaluation_node(name="f", mode="r")
        read_g_eval = self.evaluation_node(name="g", mode="r")
        script = self.evaluation_node(name="script.py")
        var_act_f = self.evaluation_node(name="f('1')")
        var_act_g = self.evaluation_node(name="g(x)")
        var_param = self.evaluation_node(name="'1'")
        var_y = self.evaluation_node(name="y")
        var_fx_w = self.evaluation_node(name="x", mode="w", first_char_line=2)
        var_gx_w = self.evaluation_node(name="x", mode="w", first_char_line=4)

        fas = self.metascript.file_accesses_store
        acc1 = fas.add_object(1, "teste", self.metascript.get_time())
        acc1.mode = "w"
        acc1.activation_id = int(var_act_f.split("_")[-1])
        acc2 = fas.add_object(1, "teste", self.metascript.get_time())
        acc2.mode = "r"
        acc2.activation_id = int(var_act_f.split("_")[-1])
        fas.do_store()
        trial = Trial()

        var_acc1 = "a_{}".format(acc1.id)

        clusterizer = Clusterizer(trial)
        clusterizer.replace_synonymer = JoinedSynonymer.create(
            AccessNameSynonymer(), SameSynonymer()
        )
        clusterizer.run()

        self.assertEqual(
            (script, cluster(script), [
                write_f_eval, write_g_eval, 
                (var_act_f, cluster(var_act_f), [
                    var_fx_w,
                    (var_act_g, cluster(var_act_g), [
                        var_gx_w,
                    ]),
                ]),
                var_acc1, var_param, var_y
            ]),
            clusterizer.main_cluster.to_tree()
        )
        created = clusterizer.created
        self.assertEqual(sorted([
            ((created[var_act_f][1], created[write_f_eval][1]), {EMPTY_ATTR}),
            ((created[var_act_g][1], created[write_g_eval][1]), {EMPTY_ATTR}),
            ((created[var_acc1][1], created[var_act_f][1]), {ACCESS_ATTR}),
            ((created[var_act_g][1], created[var_gx_w][1]), {REFERENCE_ATTR}),
            ((created[var_gx_w][1], created[var_fx_w][1]), {REFERENCE_ATTR}),
            ((created[var_y][1], created[var_act_f][1]), {REFERENCE_ATTR}),
            ((created[var_act_f][1], created[var_acc1][1]), {ACCESS_ATTR}),
            ((created[var_act_f][1], created[var_act_g][1]), {REFERENCE_ATTR}),
            ((created[var_fx_w][1], created[var_param][1]), {REFERENCE_ATTR}),
        ]), sorted([item for item in viewitems(clusterizer.dependencies)]))

    def test_file_accesses_filter_no_accesses(self):
        self.script("# script.py\n"
                    "def f(x):\n"
                    "    return g(x)\n"
                    "def g(x):\n"
                    "    return x\n"
                    "y = f('1')\n")
        self.clean_execution()

        write_f_eval = self.evaluation_node(name="f", mode="w")
        write_g_eval = self.evaluation_node(name="g", mode="w")
        read_f_eval = self.evaluation_node(name="f", mode="r")
        read_g_eval = self.evaluation_node(name="g", mode="r") 
        script = self.evaluation_node(name="script.py")
        var_act_f = self.evaluation_node(name="f('1')")
        var_act_g = self.evaluation_node(name="g(x)")
        var_param = self.evaluation_node(name="'1'")
        var_y = self.evaluation_node(name="y")
        var_fx_w = self.evaluation_node(name="x", mode="w", first_char_line=2)
        var_fx_r = self.evaluation_node(name="x", mode="r", first_char_line=3)
        var_gx_w = self.evaluation_node(name="x", mode="w", first_char_line=4)
        var_gx_r = self.evaluation_node(name="x", mode="r", first_char_line=5)
        var_str = self.evaluation_node(name=self.rtype('str'))
        var_type = self.evaluation_node(name=self.rtype('type'))
        var_function = self.evaluation_node(name=self.rtype('function'))


        fas = self.metascript.file_accesses_store
        acc1 = fas.add_object(1, "teste", self.metascript.get_time())
        acc1.mode = "w"
        acc1.activation_id = int(var_act_f.split("_")[-1])
        acc2 = fas.add_object(1, "teste2", self.metascript.get_time())
        acc2.mode = "r"
        acc2.activation_id = int(var_act_g.split("_")[-1])
        fas.do_store()
        trial = Trial()

        clusterizer = Clusterizer(trial, synonymer=Synonymer())
        clusterizer.replace_filter = FilterAccessesOut()
        clusterizer.run()

        self.assertEqual(
            (script, cluster(script), [
                write_f_eval, var_function, var_type, write_g_eval, read_f_eval,
                (var_act_f, cluster(var_act_f), [
                    var_fx_w, read_g_eval,
                    (var_act_g, cluster(var_act_g), [
                        var_gx_w, var_gx_r,
                    ]),
                    var_fx_r
                ]),
                var_param, var_str, var_y
            ]),
            clusterizer.main_cluster.to_tree()
        )
        created = clusterizer.created
        class_attr = EMPTY_ATTR.update({"label": ".__class__"})
        self.maxDiff = None
        self.assertEqual(sorted([
            ((created[read_g_eval][1], created[write_g_eval][1]), {REFERENCE_ATTR}),
            ((created[read_f_eval][1], created[write_f_eval][1]), {REFERENCE_ATTR}),
            ((created[var_act_f][1], created[read_f_eval][1]), {EMPTY_ATTR}),
            ((created[var_act_g][1], created[read_g_eval][1]), {EMPTY_ATTR}),
            ((created[var_act_g][1], created[var_gx_r][1]), {REFERENCE_ATTR}),
            ((created[var_fx_r][1], created[var_fx_w][1]), {REFERENCE_ATTR}),
            ((created[var_gx_w][1], created[var_fx_r][1]), {REFERENCE_ATTR}),
            ((created[var_gx_r][1], created[var_gx_w][1]), {REFERENCE_ATTR}),
            ((created[var_y][1], created[var_act_f][1]), {REFERENCE_ATTR}),
            ((created[write_f_eval][1], created[var_function][1]), {class_attr}),
            ((created[var_function][1], created[var_type][1]), {class_attr}),
            ((created[write_g_eval][1], created[var_function][1]), {class_attr}),
            ((created[var_act_f][1], created[var_act_g][1]), {REFERENCE_ATTR}),
            ((created[var_param][1], created[var_str][1]), {class_attr}),
            ((created[var_str][1], created[var_type][1]), {class_attr}),
            ((created[var_fx_w][1], created[var_param][1]), {REFERENCE_ATTR}),
        ]), sorted([item for item in viewitems(clusterizer.dependencies)]))

    def test_file_accesses_joined_filter_no_accesses_no_types(self):
        self.script("# script.py\n"
                    "def f(x):\n"
                    "    return g(x)\n"
                    "def g(x):\n"
                    "    return x\n"
                    "y = f('1')\n")
        self.clean_execution()

        write_f_eval = self.evaluation_node(name="f", mode="w")
        write_g_eval = self.evaluation_node(name="g", mode="w")
        read_f_eval = self.evaluation_node(name="f", mode="r")
        read_g_eval = self.evaluation_node(name="g", mode="r")
        script = self.evaluation_node(name="script.py")
        var_act_f = self.evaluation_node(name="f('1')")
        var_act_g = self.evaluation_node(name="g(x)")
        var_param = self.evaluation_node(name="'1'")
        var_y = self.evaluation_node(name="y")
        var_fx_w = self.evaluation_node(name="x", mode="w", first_char_line=2)
        var_fx_r = self.evaluation_node(name="x", mode="r", first_char_line=3)
        var_gx_w = self.evaluation_node(name="x", mode="w", first_char_line=4)
        var_gx_r = self.evaluation_node(name="x", mode="r", first_char_line=5)

        fas = self.metascript.file_accesses_store
        acc1 = fas.add_object(1, "teste", self.metascript.get_time())
        acc1.mode = "w"
        acc1.activation_id = int(var_act_f.split("_")[-1])
        acc2 = fas.add_object(1, "teste2", self.metascript.get_time())
        acc2.mode = "r"
        acc2.activation_id = int(var_act_g.split("_")[-1])
        fas.do_store()
        trial = Trial()

        clusterizer = Clusterizer(trial, synonymer=Synonymer())
        clusterizer.replace_filter = JoinedFilter.create(
            FilterAccessesOut(), FilterTypesOut()
        )
        clusterizer.run()

        self.assertEqual(
            (script, cluster(script), [
                write_f_eval, write_g_eval, read_f_eval, 
                (var_act_f, cluster(var_act_f), [
                    var_fx_w, read_g_eval,
                    (var_act_g, cluster(var_act_g), [
                        var_gx_w, var_gx_r,
                    ]),
                    var_fx_r
                ]),
                var_param, var_y
            ]),
            clusterizer.main_cluster.to_tree()
        )
        created = clusterizer.created
        self.assertEqual(sorted([
            ((created[var_act_g][1], created[read_g_eval][1]), {EMPTY_ATTR}),
            ((created[var_act_g][1], created[var_gx_r][1]), {REFERENCE_ATTR}),
            ((created[read_g_eval][1], created[write_g_eval][1]), {REFERENCE_ATTR}),
            ((created[var_fx_r][1], created[var_fx_w][1]), {REFERENCE_ATTR}),
            ((created[var_gx_w][1], created[var_fx_r][1]), {REFERENCE_ATTR}),
            ((created[var_gx_r][1], created[var_gx_w][1]), {REFERENCE_ATTR}),
            ((created[var_y][1], created[var_act_f][1]), {REFERENCE_ATTR}),
            ((created[var_act_f][1], created[var_act_g][1]), {REFERENCE_ATTR}),
            ((created[var_act_f][1], created[read_f_eval][1]), {EMPTY_ATTR}),
            ((created[read_f_eval][1], created[write_f_eval][1]), {REFERENCE_ATTR}),
            ((created[var_fx_w][1], created[var_param][1]), {REFERENCE_ATTR}),
        ]), sorted([item for item in viewitems(clusterizer.dependencies)]))

    def test_user_activation_rank_lines(self):
        self.script("# script.py\n"
                    "def f(x):\n"
                    "    return x + x\n"
                    "y = f('1') + '1'\n")
        self.clean_execution()

        write_f_eval = self.evaluation_node(name="f", mode="w")
        read_f_eval = self.evaluation_node(name="f", mode="r")
        script = self.evaluation_node(name="script.py")
        var_act = self.evaluation_node(name="f('1')")
        var_param = self.evaluation_node(name="'1'", first_char_column=6)
        var_add_1 = self.evaluation_node(name="'1'", first_char_column=13)
        var_y = self.evaluation_node(name="y")
        var_x_w = self.evaluation_node(name="x", mode="w")
        var_x_r1 = self.evaluation_node(name="x", first_char_column=11)
        var_x_r2 = self.evaluation_node(name="x", first_char_column=15)
        var_x_sum = self.evaluation_node(name="x + x")
        var_concat = self.evaluation_node(name="f('1') + '1'")

        trial = Trial()
        clusterizer = Clusterizer(trial, synonymer=Synonymer())
        clusterizer.config.rank_option = 1
        clusterizer.run()

        self.assertEqual(
             (script, cluster(script), [
                write_f_eval,
                read_f_eval,
                (var_act, cluster(var_act),
                    [var_x_w, var_x_r1, var_x_r2, var_x_sum]),
                var_param, var_add_1, var_concat, var_y
            ]),
            clusterizer.main_cluster.to_tree()
        )
        created = clusterizer.created
        expected = [
            ((created[var_x_r1][1], created[var_x_w][1]), {REFERENCE_ATTR}),
            ((created[var_x_r2][1], created[var_x_w][1]), {REFERENCE_ATTR}),
            ((created[var_x_sum][1], created[var_x_r1][1]), {EMPTY_ATTR}),
            ((created[var_x_sum][1], created[var_x_r2][1]), {EMPTY_ATTR}),
            ((created[var_concat][1], created[var_add_1][1]), {EMPTY_ATTR}),
            ((created[var_concat][1], created[var_act][1]), {EMPTY_ATTR}),
            ((created[var_y][1], created[var_concat][1]), {REFERENCE_ATTR}),
            ((created[read_f_eval][1], created[write_f_eval][1]), {REFERENCE_ATTR}),
            ((created[var_act][1], created[var_x_sum][1]), {REFERENCE_ATTR}),
            ((created[var_act][1], created[read_f_eval][1]), {EMPTY_ATTR}),
            ((created[var_x_w][1], created[var_param][1]), {REFERENCE_ATTR}),
        ]
        result = sorted([item for item in viewitems(clusterizer.dependencies)])
        self.assertEqual(expected, result)
        

        self.assertEqual([created[write_f_eval][1]], created[script][1].ranks[0])
        self.assertEqual([
            created[read_f_eval][1], created[var_act][1], created[var_param][1], 
            created[var_add_1][1], created[var_concat][1], created[var_y][1], 
        ], created[script][1].ranks[1])
        self.assertEqual([created[var_x_w][1]], created[var_act][1].ranks[0])
        self.assertEqual([
            created[var_x_r1][1], created[var_x_r2][1], created[var_x_sum][1],
        ], created[var_act][1].ranks[1])
