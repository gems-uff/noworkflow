# Copyright (c) 2017 Universidade Federal Fluminense (UFF)
# Copyright (c) 2017 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""Test dependency clusterizer"""
from __future__ import (absolute_import, print_function,
                        division, unicode_literals)

from future.utils import viewitems

from ...now.persistence.models import Trial
from ...now.models.dependency_graph.attributes import EMPTY_ATTR, ACCESS_ATTR
from ...now.models.dependency_graph.attributes import PROPAGATED_ATTR
from ...now.models.dependency_graph.attributes import REFERENCE_ATTR
from ...now.models.dependency_graph.clusterizer import DependencyClusterizer
from ...now.models.dependency_graph.synonymers import Synonymer

from ..collection_testcase import CollectionTestCase, cluster


CLASS_ATTR = EMPTY_ATTR.update({"label": ".__class__"})


class TestDependencyClusterizer(CollectionTestCase):
    """Test Dependency Clusterizer"""
    # pylint: disable=missing-docstring
    # pylint: disable=invalid-name
    # pylint: disable=too-many-public-methods

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
        var_int = self.evaluation_node(name=self.rtype('int'))
        var_type = self.evaluation_node(name=self.rtype('type'))
        var_module = self.evaluation_node(name=self.rtype('module'))

        trial = Trial()
        clusterizer = DependencyClusterizer(trial, synonymer=Synonymer()).run()

        self.assertEqual(
            (script, cluster(script),
                [num1, var_int, var_type, var_module, vara_w, vara_r, varb_w, varb_r, varc_w]),
            clusterizer.main_cluster.to_tree()
        )
        created = clusterizer.created
        self.assertEqual([
            ((created[var_module][1], created[var_type][1]), {CLASS_ATTR}),
            ((created[num1][1], created[var_int][1]), {CLASS_ATTR}),
            ((created[var_int][1], created[var_type][1]), {CLASS_ATTR}),
            ((created[vara_w][1], created[num1][1]), {REFERENCE_ATTR}),
            ((created[vara_r][1], created[vara_w][1]), {REFERENCE_ATTR}),
            ((created[varb_w][1], created[vara_r][1]), {REFERENCE_ATTR}),
            ((created[varb_r][1], created[varb_w][1]), {REFERENCE_ATTR}),
            ((created[varc_w][1], created[varb_r][1]), {REFERENCE_ATTR}),
        ], sorted([item for item in viewitems(clusterizer.dependencies)]))

    def test_single_activation(self):
        self.script("# script.py\n"
                    "int()\n")
        self.clean_execution()

        script = self.evaluation_node(name="script.py")
        var_act = self.evaluation_node(name="int()")
        var_read_int = self.evaluation_node(name='int', mode="r")
        var_write_int = self.evaluation_node(name='int', mode="w")
        var_type = self.evaluation_node(name=self.rtype('type'))
        var_module = self.evaluation_node(name=self.rtype('module'))

        trial = Trial()
        clusterizer = DependencyClusterizer(trial, synonymer=Synonymer()).run()

        self.assertEqual(
            (script, cluster(script), [var_write_int, var_act, var_type, var_module, var_read_int]),
            clusterizer.main_cluster.to_tree()
        )
        created = clusterizer.created
        self.assertEqual(sorted([
            ((created[var_act][1], created[var_write_int][1]), {CLASS_ATTR}),
            ((created[var_read_int][1], created[var_write_int][1]), {REFERENCE_ATTR}),
            ((created[var_act][1], created[var_read_int][1]), {EMPTY_ATTR}),
            ((created[var_write_int][1], created[var_type][1]), {CLASS_ATTR}),
            ((created[var_module][1], created[var_type][1]), {CLASS_ATTR}),
        ]), sorted([item for item in viewitems(clusterizer.dependencies)]))

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
        var_str = self.evaluation_node(name=self.rtype('str'))
        var_type = self.evaluation_node(name=self.rtype('type'))
        var_function = self.evaluation_node(name=self.rtype('function'))
        var_module = self.evaluation_node(name=self.rtype('module'))

        trial = Trial()
        clusterizer = DependencyClusterizer(trial, synonymer=Synonymer())
        clusterizer.config.max_depth = 1
        clusterizer.run()

        self.assertEqual(
            (script, cluster(script),
                [write_f_eval, read_f_eval, var_param, var_act, var_y]),
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
        var_x_w = self.evaluation_node(name="x", mode="w")
        var_x_r = self.evaluation_node(name="x", mode="r")
        var_y = self.evaluation_node(name="y")
        var_str = self.evaluation_node(name=self.rtype('str'))
        var_type = self.evaluation_node(name=self.rtype('type'))
        var_function = self.evaluation_node(name=self.rtype('function'))
        var_module = self.evaluation_node(name=self.rtype('module'))

        trial = Trial()
        clusterizer = DependencyClusterizer(trial, synonymer=Synonymer())
        clusterizer.run()

        self.assertEqual(
            (script, cluster(script),
                [write_f_eval, var_function, var_type, var_str, var_param,
                 var_module, read_f_eval, var_act, var_x_w, var_x_r, var_y]),
            clusterizer.main_cluster.to_tree()
        )
        created = clusterizer.created
        self.assertEqual(sorted([
            ((created[read_f_eval][1], created[write_f_eval][1]), {REFERENCE_ATTR}),
            ((created[var_act][1], created[read_f_eval][1]), {EMPTY_ATTR}),
            ((created[var_y][1], created[var_act][1]), {REFERENCE_ATTR}),
            ((created[var_module][1], created[var_type][1]), {CLASS_ATTR}),
            ((created[write_f_eval][1], created[var_function][1]), {CLASS_ATTR}),
            ((created[var_function][1], created[var_type][1]), {CLASS_ATTR}),
            ((created[var_act][1], created[var_param][1]), {REFERENCE_ATTR}),
            ((created[var_act][1], created[var_x_r][1]), {REFERENCE_ATTR}),
            ((created[var_param][1], created[var_str][1]), {CLASS_ATTR}),
            ((created[var_str][1], created[var_type][1]), {CLASS_ATTR}),
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
        trial_id = self.clean_execution()

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
        var_module = self.evaluation_node(name=self.rtype('module'))

        fas = self.metascript.file_accesses_store
        acc1 = fas.add_object(trial_id, "teste", self.metascript.get_time())
        acc1.mode = "w"
        acc1.activation_id = int(var_act_f.split("_")[-1])
        acc2 = fas.add_object(trial_id, "teste2", self.metascript.get_time())
        acc2.mode = "r"
        acc2.activation_id = int(var_act_g.split("_")[-1])
        fas.do_store()
        trial = Trial()

        var_acc1 = "a_{}".format(acc1.id)
        var_acc2 = "a_{}".format(acc2.id)

        clusterizer = DependencyClusterizer(trial, synonymer=Synonymer())
        clusterizer.run()

        self.assertEqual(
            (script, cluster(script), [
                write_f_eval, var_function, write_g_eval, var_type, var_str, 
                var_param, var_module, read_f_eval, var_act_f, var_acc1, var_fx_w, 
                read_g_eval, var_fx_r, var_act_g, var_acc2,  var_gx_w, var_gx_r, var_y,
            ]),
            clusterizer.main_cluster.to_tree()
        )
        created = clusterizer.created
        self.assertEqual(sorted([
            ((created[read_f_eval][1], created[write_f_eval][1]), {REFERENCE_ATTR}),
            ((created[read_g_eval][1], created[write_g_eval][1]), {REFERENCE_ATTR}),
            ((created[var_act_f][1], created[read_f_eval][1]), {EMPTY_ATTR}),
            ((created[var_act_g][1], created[read_g_eval][1]), {EMPTY_ATTR}),
            ((created[var_acc1][1], created[var_act_f][1]), {ACCESS_ATTR}),
            ((created[var_act_g][1], created[var_acc2][1]), {ACCESS_ATTR}),
            ((created[var_act_g][1], created[var_fx_r][1]), {REFERENCE_ATTR}),
            ((created[var_act_g][1], created[var_gx_r][1]), {REFERENCE_ATTR}),
            ((created[var_fx_r][1], created[var_fx_w][1]), {REFERENCE_ATTR}),
            ((created[var_gx_w][1], created[var_fx_r][1]), {REFERENCE_ATTR}),
            ((created[var_gx_r][1], created[var_gx_w][1]), {REFERENCE_ATTR}),
            ((created[var_y][1], created[var_act_f][1]), {REFERENCE_ATTR}),
            ((created[var_module][1], created[var_type][1]), {CLASS_ATTR}),
            ((created[write_f_eval][1], created[var_function][1]), {CLASS_ATTR}),
            ((created[var_function][1], created[var_type][1]), {CLASS_ATTR}),
            ((created[write_g_eval][1], created[var_function][1]), {CLASS_ATTR}),
            ((created[var_act_f][1], created[var_act_g][1]), {REFERENCE_ATTR}),
            ((created[var_act_f][1], created[var_param][1]), {REFERENCE_ATTR}),
            ((created[var_param][1], created[var_str][1]), {CLASS_ATTR}),
            ((created[var_str][1], created[var_type][1]), {CLASS_ATTR}),
            ((created[var_fx_w][1], created[var_param][1]), {REFERENCE_ATTR}),
        ]), sorted([item for item in viewitems(clusterizer.dependencies)]))

    def test_file_accesses_max_depth_2(self):
        self.script("# script.py\n"
                    "def f(x):\n"
                    "    return g(x)\n"
                    "def g(x):\n"
                    "    return x\n"
                    "y = f('1')\n")
        trial_id = self.clean_execution()

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
        acc1 = fas.add_object(trial_id, "teste", self.metascript.get_time())
        acc1.mode = "w"
        acc1.activation_id = int(var_act_f.split("_")[-1])
        acc2 = fas.add_object(trial_id, "teste2", self.metascript.get_time())
        acc2.mode = "r"
        acc2.activation_id = int(var_act_g.split("_")[-1])
        fas.do_store()
        trial = Trial()

        var_acc1 = "a_{}".format(acc1.id)
        var_acc2 = "a_{}".format(acc2.id)

        clusterizer = DependencyClusterizer(trial, synonymer=Synonymer())
        clusterizer.config.max_depth = 2
        clusterizer.run()

        self.assertEqual(
            (script, cluster(script), [
                write_f_eval, write_g_eval, read_f_eval, var_param, var_act_f, var_fx_w, read_g_eval, 
                var_fx_r, var_act_g, var_acc2,  var_acc1,  var_y
            ]),
            clusterizer.main_cluster.to_tree()
        )
        created = clusterizer.created
        self.assertEqual(sorted([
            ((created[read_f_eval][1], created[write_f_eval][1]), {REFERENCE_ATTR}),
            ((created[read_g_eval][1], created[write_g_eval][1]), {REFERENCE_ATTR}),
            ((created[var_act_f][1], created[read_f_eval][1]), {EMPTY_ATTR}),
            ((created[var_act_g][1], created[read_g_eval][1]), {EMPTY_ATTR}),
            ((created[var_acc1][1], created[var_act_f][1]), {ACCESS_ATTR}),
            ((created[var_act_g][1], created[var_acc2][1]), {ACCESS_ATTR}),
            ((created[var_act_g][1], created[var_fx_r][1]),
                {REFERENCE_ATTR, PROPAGATED_ATTR}),
            ((created[var_fx_r][1], created[var_fx_w][1]), {REFERENCE_ATTR}),
            ((created[var_y][1], created[var_act_f][1]), {REFERENCE_ATTR}),
            ((created[var_act_f][1], created[var_act_g][1]), {REFERENCE_ATTR}),
            ((created[var_act_f][1], created[var_param][1]), {REFERENCE_ATTR}),
            ((created[var_fx_w][1], created[var_param][1]), {REFERENCE_ATTR}),
        ]), sorted([item for item in viewitems(clusterizer.dependencies)]))

    def test_file_accesses_max_depth_1(self):
        self.script("# script.py\n"
                    "def f(x):\n"
                    "    return g(x)\n"
                    "def g(x):\n"
                    "    return x\n"
                    "y = f('1')\n")
        trial_id = self.clean_execution()

        write_f_eval = self.evaluation_node(name="f", mode="w")
        write_g_eval = self.evaluation_node(name="g", mode="w")
        read_f_eval = self.evaluation_node(name="f", mode="r")
        script = self.evaluation_node(name="script.py")
        var_act_f = self.evaluation_node(name="f('1')")
        var_act_g = self.evaluation_node(name="g(x)")
        var_param = self.evaluation_node(name="'1'")
        var_y = self.evaluation_node(name="y")

        fas = self.metascript.file_accesses_store
        acc1 = fas.add_object(trial_id, "teste", self.metascript.get_time())
        acc1.mode = "w"
        acc1.activation_id = int(var_act_f.split("_")[-1])
        acc2 = fas.add_object(trial_id, "teste2", self.metascript.get_time())
        acc2.mode = "r"
        acc2.activation_id = int(var_act_g.split("_")[-1])
        fas.do_store()
        trial = Trial()

        var_acc1 = "a_{}".format(acc1.id)
        var_acc2 = "a_{}".format(acc2.id)

        clusterizer = DependencyClusterizer(trial, synonymer=Synonymer())
        clusterizer.config.max_depth = 1
        clusterizer.run()

        self.assertEqual(
            (script, cluster(script), [
                write_f_eval, write_g_eval, read_f_eval, var_param, var_act_f,
                var_acc1, var_acc2, var_y
            ]),
            clusterizer.main_cluster.to_tree()
        )
        created = clusterizer.created
        self.assertEqual(sorted([
            ((created[var_acc1][1], created[var_act_f][1]), {ACCESS_ATTR}),
            ((created[var_y][1], created[var_act_f][1]), {REFERENCE_ATTR}),
            ((created[read_f_eval][1], created[write_f_eval][1]), {REFERENCE_ATTR}),
            ((created[var_act_f][1], created[read_f_eval][1]),
                {EMPTY_ATTR}),
            ((created[var_act_f][1], created[write_g_eval][1]),
                {PROPAGATED_ATTR, REFERENCE_ATTR, EMPTY_ATTR}),
            ((created[var_act_f][1], created[var_acc2][1]),
                {ACCESS_ATTR, PROPAGATED_ATTR}),
            ((created[var_act_f][1], created[var_param][1]),
                {REFERENCE_ATTR, PROPAGATED_ATTR}),
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
        var_str = self.evaluation_node(name=self.rtype('str'))
        var_type = self.evaluation_node(name=self.rtype('type'))
        var_function = self.evaluation_node(name=self.rtype('function'))
        var_module = self.evaluation_node(name=self.rtype('module'))

        trial = Trial()
        clusterizer = DependencyClusterizer(trial, synonymer=Synonymer())
        clusterizer.config.rank_option = 1
        clusterizer.run()

        self.assertEqual(
            (script, cluster(script), [
                write_f_eval, var_function, var_type, var_str, var_param,
                var_x_sum, var_act, var_add_1, var_concat, var_module, 
                read_f_eval,
                var_x_w, var_x_r1, var_x_r2, var_y
            ]),
            clusterizer.main_cluster.to_tree()
        )
        created = clusterizer.created
        self.maxDiff = None
        self.assertEqual(sorted([
            ((created[var_x_r2][1], created[var_x_w][1]), {REFERENCE_ATTR}),
            ((created[var_x_sum][1], created[var_x_r2][1]), {EMPTY_ATTR}),
            ((created[var_x_sum][1], created[var_str][1]), {CLASS_ATTR}),
            ((created[var_x_sum][1], created[var_x_r1][1]), {EMPTY_ATTR}),
            ((created[var_add_1][1], created[var_str][1]), {CLASS_ATTR}),
            ((created[var_concat][1], created[var_add_1][1]), {EMPTY_ATTR}),
            ((created[var_concat][1], created[var_act][1]), {EMPTY_ATTR}),
            ((created[var_concat][1], created[var_str][1]), {CLASS_ATTR}),
            ((created[var_y][1], created[var_concat][1]), {REFERENCE_ATTR}),
            ((created[var_module][1], created[var_type][1]), {CLASS_ATTR}),
            ((created[write_f_eval][1], created[var_function][1]), {CLASS_ATTR}),
            ((created[var_function][1], created[var_type][1]), {CLASS_ATTR}),
            ((created[read_f_eval][1], created[write_f_eval][1]), {REFERENCE_ATTR}),
            ((created[var_act][1], created[var_x_sum][1]), {REFERENCE_ATTR}),
            ((created[var_act][1], created[var_param][1]), {EMPTY_ATTR}),
            ((created[var_act][1], created[read_f_eval][1]), {EMPTY_ATTR}),
            ((created[var_act][1], created[var_str][1]), {CLASS_ATTR}),
            ((created[var_param][1], created[var_str][1]), {CLASS_ATTR}),
            ((created[var_str][1], created[var_type][1]), {CLASS_ATTR}),
            ((created[var_x_w][1], created[var_param][1]), {REFERENCE_ATTR}),
            ((created[var_x_r1][1], created[var_x_w][1]), {REFERENCE_ATTR}),
        ]), sorted([item for item in viewitems(clusterizer.dependencies)]))

        ranks = sorted([
            sorted(x) for x in created[script][1].ranks
        ])

        self.assertEqual(sorted([
            created[var_x_r2][1], created[var_x_sum][1], created[var_x_r1][1], 
        ]), ranks[0])
        self.assertEqual(sorted([
            created[var_add_1][1], created[var_concat][1], created[var_y][1],
            created[var_act][1], created[read_f_eval][1],  created[var_param][1], 
        ]), ranks[1])
        self.assertEqual([
            created[var_module][1], created[var_function][1],
            created[var_type][1], created[var_str][1],
        ], ranks[2])
        self.assertEqual([
            created[write_f_eval][1], created[var_x_w][1]
        ], ranks[3])

