# Copyright (c) 2017 Universidade Federal Fluminense (UFF)
# Copyright (c) 2017 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""Test dataflow clusterizer"""
from __future__ import (absolute_import, print_function,
                        division, unicode_literals)

from future.utils import viewitems

from ...now.persistence.models import Trial
from ...now.models.dependency_graph.synonymers import SameSynonymer
from ...now.models.dependency_graph.synonymers import AccessNameSynonymer
from ...now.models.dependency_graph.synonymers import JoinedSynonymer
from ...now.models.dependency_graph.filters import FilterAccessesOut
from ...now.models.dependency_graph.filters import JoinedFilter
from ...now.models.dependency_graph.attributes import EMPTY_ATTR, ACCESS_ATTR
from ...now.models.dependency_graph.attributes import PROPAGATED_ATTR
from ...now.models.dependency_graph.attributes import REFERENCE_ATTR
from ...now.models.dependency_graph.clusterizer import ProspectiveClusterizer

from ..collection_testcase import CollectionTestCase, cluster


class TestProspectiveClusterizer(CollectionTestCase):
    """Test Dataflow Clusterizer"""
    # pylint: disable=missing-docstring
    # pylint: disable=invalid-name
    # pylint: disable=too-many-public-methods

    def test_evaluations_should_not_appear_if_there_is_no_activation(self):
        self.script("# script.py\n"
                    "a = 1\n"
                    "b = a\n"
                    "c = b\n")
        self.clean_execution()

        script = self.evaluation_node(name="script.py")

        trial = Trial()
        clusterizer = ProspectiveClusterizer(trial).run()

        self.assertEqual(
            (script, cluster(script), []),
            clusterizer.main_cluster.to_tree()
        )
        self.assertEqual({}, clusterizer.dependencies)

    def test_single_activation(self):
        self.script("# script.py\n"
                    "int()\n")
        self.clean_execution()

        script = self.evaluation_node(name="script.py")
        var_act = self.evaluation_node(name="int()")
        var_int = self.evaluation_node(name="int", mode='w')

        trial = Trial()
        clusterizer = ProspectiveClusterizer(trial).run()

        self.assertEqual(
            (script, cluster(script), [var_act, var_int]),
            clusterizer.main_cluster.to_tree()
        )
        created = clusterizer.created
        self.assertEqual(sorted([
            ((created[var_act][1], created[var_int][1]), {EMPTY_ATTR, EMPTY_ATTR.update({'label':'.__class__'})}),
        ]), sorted([item for item in viewitems(clusterizer.dependencies)]))


    def test_single_activation_dependencies(self):
        self.script("# script.py\n"
                    "x = int('1')\n")
        self.clean_execution()

        script = self.evaluation_node(name="script.py")
        var_act = self.evaluation_node(name="int('1')")
        var_int = self.evaluation_node(name="int", mode='w')
        var_param = self.evaluation_node(name="'1'")
        var_x = self.evaluation_node(name="x")

        trial = Trial()
        clusterizer = ProspectiveClusterizer(trial).run()

        self.assertEqual(
            (script, cluster(script), [var_act, var_int, var_param, var_x]),
            clusterizer.main_cluster.to_tree()
        )
        created = clusterizer.created
        self.assertEqual(sorted([
            ((created[var_act][1], created[var_param][1]), {EMPTY_ATTR}),
            ((created[var_act][1], created[var_int][1]), {EMPTY_ATTR, EMPTY_ATTR.update({'label':'.__class__'})}),
            ((created[var_x][1], created[var_act][1]), {REFERENCE_ATTR}),
        ]), sorted([item for item in viewitems(clusterizer.dependencies)]))

    def test_user_activation_max_depth_1(self):
        self.script("# script.py\n"
                    "def f(x):\n"
                    "    return x\n"
                    "y = f('1')\n")
        self.clean_execution()

        script = self.evaluation_node(name="script.py")
        var_f = self.evaluation_node(name="f", mode='w')
        var_act = self.evaluation_node(name="f('1')")
        var_param = self.evaluation_node(name="'1'")
        var_y = self.evaluation_node(name="y")

        trial = Trial()
        clusterizer = ProspectiveClusterizer(trial)
        clusterizer.config.max_depth = 1
        clusterizer.run()
        self.assertEqual(
            (script, cluster(script), [var_act, var_f, var_param, var_y]),
            clusterizer.main_cluster.to_tree()
        )
        created = clusterizer.created
        self.assertEqual(sorted([
            ((created[var_y][1], created[var_act][1]), {REFERENCE_ATTR}),
            ((created[var_act][1], created[var_f][1]), {EMPTY_ATTR}),
            ((created[var_act][1], created[var_param][1]),
                {REFERENCE_ATTR, PROPAGATED_ATTR}),
        ]), sorted([item for item in viewitems(clusterizer.dependencies)]))

    def test_user_activation_no_max_depth(self):
        self.script("# script.py\n"
                    "def f(x):\n"
                    "    return x\n"
                    "y = f('1')\n")
        self.clean_execution()

        script = self.evaluation_node(name="script.py")
        var_f = self.evaluation_node(name="f", mode='w')
        var_act = self.evaluation_node(name="f('1')")
        var_param = self.evaluation_node(name="'1'")
        var_y = self.evaluation_node(name="y")
        var_x_w = self.evaluation_node(name="x", mode="w")

        trial = Trial()
        clusterizer = ProspectiveClusterizer(trial)
        clusterizer.run()

        self.assertEqual(
            (script, cluster(script), [
                (var_act, cluster(var_act), [var_x_w]),
                var_f, var_param, var_y
            ]),
            clusterizer.main_cluster.to_tree()
        )
        created = clusterizer.created
        self.assertEqual(sorted([
            ((created[var_y][1], created[var_act][1]), {REFERENCE_ATTR}),
            ((created[var_act][1], created[var_x_w][1]), {REFERENCE_ATTR}),
            ((created[var_act][1], created[var_f][1]), {EMPTY_ATTR}),
            ((created[var_x_w][1], created[var_param][1]), {REFERENCE_ATTR}),
        ]), sorted([item for item in viewitems(clusterizer.dependencies)]))

    def test_user_activation_no_dependency(self):
        # Should we connect e_3 to e_4 (argument)?
        self.script("# script.py\n"
                    "def f(x):\n"
                    "    return\n"
                    "y = f('1')\n")
        self.clean_execution()

        script = self.evaluation_node(name="script.py")
        var_f = self.evaluation_node(name="f", mode='w')
        var_act = self.evaluation_node(name="f('1')")
        var_param = self.evaluation_node(name="'1'")
        var_y = self.evaluation_node(name="y")
        var_x_w = self.evaluation_node(name="x", mode="w")

        trial = Trial()
        clusterizer = ProspectiveClusterizer(trial)
        clusterizer.run()

        self.assertEqual(
            (script, cluster(script), [
                (var_act, cluster(var_act), []),
                var_f, var_param, var_y
            ]),
            clusterizer.main_cluster.to_tree()
        )
        created = clusterizer.created
        self.assertEqual(sorted([
            ((created[var_act][1], created[var_f][1]), {EMPTY_ATTR}),
            ((created[var_y][1], created[var_act][1]), {REFERENCE_ATTR}),
        ]), sorted([item for item in viewitems(clusterizer.dependencies)]))

    def test_file_accesses(self):
        self.script("# script.py\n"
                    "def f(x):\n"
                    "    return g(x)\n"
                    "def g(x):\n"
                    "    return x\n"
                    "y = f('1')\n")
        self.clean_execution()

        script = self.evaluation_node(name="script.py")
        var_f = self.evaluation_node(name="f", mode='w')
        var_g = self.evaluation_node(name="g", mode='w')
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
        acc2 = fas.add_object(1, "teste2", self.metascript.get_time())
        acc2.mode = "r"
        acc2.activation_id = int(var_act_g.split("_")[-1])
        fas.do_store()
        trial = Trial()

        var_acc1 = "a_{}".format(acc1.id)
        var_acc2 = "a_{}".format(acc2.id)

        clusterizer = ProspectiveClusterizer(trial)
        clusterizer.run()

        self.assertEqual(
            (script, cluster(script), [
                (var_act_f, cluster(var_act_f), [
                    (var_act_g, cluster(var_act_g), [
                        var_gx_w,
                    ]),
                    var_acc2, var_g, var_fx_w,
                ]),
                var_acc1, var_f, var_param, var_y
            ]),
            clusterizer.main_cluster.to_tree()
        )
        created = clusterizer.created
        self.assertEqual(sorted([
            ((created[var_act_g][1], created[var_g][1]), {EMPTY_ATTR}),
            ((created[var_act_f][1], created[var_f][1]), {EMPTY_ATTR}),
            ((created[var_acc1][1], created[var_act_f][1]), {ACCESS_ATTR}),
            ((created[var_act_g][1], created[var_acc2][1]), {ACCESS_ATTR}),
            ((created[var_act_g][1], created[var_gx_w][1]), {REFERENCE_ATTR}),
            ((created[var_gx_w][1], created[var_fx_w][1]), {REFERENCE_ATTR}),
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

        script = self.evaluation_node(name="script.py")
        var_f = self.evaluation_node(name="f", mode='w')
        var_g = self.evaluation_node(name="g", mode='w')
        var_act_f = self.evaluation_node(name="f('1')")
        var_act_g = self.evaluation_node(name="g(x)")
        var_param = self.evaluation_node(name="'1'")
        var_y = self.evaluation_node(name="y")
        var_fx_w = self.evaluation_node(name="x", mode="w", first_char_line=2)

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

        clusterizer = ProspectiveClusterizer(trial)
        clusterizer.config.max_depth = 2
        clusterizer.run()

        self.assertEqual(
            (script, cluster(script), [
                (var_act_f, cluster(var_act_f), [
                    var_act_g, var_acc2, var_g, var_fx_w,
                ]),
                var_acc1, var_f, var_param, var_y
            ]),
            clusterizer.main_cluster.to_tree()
        )
        created = clusterizer.created
        self.assertEqual(sorted([
            ((created[var_acc1][1], created[var_act_f][1]), {ACCESS_ATTR}),
            ((created[var_act_g][1], created[var_g][1]), {EMPTY_ATTR}),
            ((created[var_act_g][1], created[var_acc2][1]), {ACCESS_ATTR}),
            ((created[var_act_g][1], created[var_fx_w][1]), {REFERENCE_ATTR, PROPAGATED_ATTR}),
            ((created[var_y][1], created[var_act_f][1]), {REFERENCE_ATTR}),
            ((created[var_act_f][1], created[var_act_g][1]), {REFERENCE_ATTR}),
            ((created[var_act_f][1], created[var_f][1]), {EMPTY_ATTR}),
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

        script = self.evaluation_node(name="script.py")
        var_f = self.evaluation_node(name="f", mode='w')
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

        clusterizer = ProspectiveClusterizer(trial)
        clusterizer.config.max_depth = 1
        clusterizer.run()

        self.assertEqual(
            (script, cluster(script), [
                var_act_f,
                var_acc1, var_acc2, var_f, var_param, var_y
            ]),
            clusterizer.main_cluster.to_tree()
        )
        created = clusterizer.created
        self.assertEqual(sorted([
            ((created[var_acc1][1], created[var_act_f][1]), {ACCESS_ATTR}),
            ((created[var_y][1], created[var_act_f][1]), {REFERENCE_ATTR}),
            ((created[var_act_f][1], created[var_acc2][1]), {ACCESS_ATTR}),
            ((created[var_act_f][1], created[var_param][1]),
                {REFERENCE_ATTR, PROPAGATED_ATTR}),
            ((created[var_act_f][1], created[var_f][1]),
                {EMPTY_ATTR}),
        ]), sorted([item for item in viewitems(clusterizer.dependencies)]))

    def test_user_activation_rank_lines(self):
        self.script("# script.py\n"
                    "def f(x):\n"
                    "    return x + x\n"
                    "y = f('1') + '1'\n")
        self.clean_execution()

        script = self.evaluation_node(name="script.py")
        var_act = self.evaluation_node(name="f('1')")
        var_f = self.evaluation_node(name="f")
        var_param = self.evaluation_node(name="'1'", first_char_column=6)
        var_add_1 = self.evaluation_node(name="'1'", first_char_column=13)
        var_y = self.evaluation_node(name="y")
        var_x_w = self.evaluation_node(name="x", mode="w")
        var_x_r1 = self.evaluation_node(name="x", first_char_column=11)
        var_x_r2 = self.evaluation_node(name="x", first_char_column=15)
        var_x_sum = self.evaluation_node(name="x + x")
        var_concat = self.evaluation_node(name="f('1') + '1'")

        trial = Trial()
        clusterizer = ProspectiveClusterizer(trial)
        clusterizer.config.rank_option = 1
        clusterizer.run()

        self.assertEqual(
            (script, cluster(script), [
                (var_act, cluster(var_act), [var_x_sum]),
                var_f, var_param, var_concat,
            ]),
            clusterizer.main_cluster.to_tree()
        )
        created = clusterizer.created
        self.assertEqual(sorted([
            ((created[var_x_sum][1], created[var_param][1]),
                {EMPTY_ATTR, REFERENCE_ATTR, PROPAGATED_ATTR}),
            ((created[var_concat][1], created[var_act][1]), {EMPTY_ATTR}),
            ((created[var_act][1], created[var_x_sum][1]), {REFERENCE_ATTR}),
            ((created[var_act][1], created[var_f][1]), {EMPTY_ATTR}),
        ]), sorted([item for item in viewitems(clusterizer.dependencies)]))

        self.assertEqual([
            created[var_act][1], created[var_param][1], created[var_concat][1],
        ], created[script][1].ranks[0])
        self.assertEqual([
            created[var_x_sum][1],
        ], created[var_act][1].ranks[0])
