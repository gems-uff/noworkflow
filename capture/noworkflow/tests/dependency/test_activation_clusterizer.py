# Copyright (c) 2017 Universidade Federal Fluminense (UFF)
# Copyright (c) 2017 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""Test activation clusterizer"""
from __future__ import (absolute_import, print_function,
                        division, unicode_literals)

from future.utils import viewitems

from ...now.persistence.models import Trial
from ...now.models.dependency_graph.attributes import EMPTY_ATTR, ACCESS_ATTR
from ...now.models.dependency_graph.attributes import REFERENCE_ATTR
from ...now.models.dependency_graph.clusterizer import ActivationClusterizer

from ..collection_testcase import CollectionTestCase, cluster


class TestActivationClusterizer(CollectionTestCase):
    """Test Activation Clusterizer"""
    # pylint: disable=missing-docstring
    # pylint: disable=invalid-name
    # pylint: disable=too-many-public-methods

    def test_main_activation(self):
        self.script("# script.py\n"
                    "a = 1\n"
                    "b = a\n"
                    "c = b\n")
        self.clean_execution()

        script = self.evaluation_node(name="script.py")

        trial = Trial()
        clusterizer = ActivationClusterizer(trial).run()

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

        trial = Trial()
        clusterizer = ActivationClusterizer(trial).run()

        self.assertEqual(
            (script, cluster(script), [var_act]),
            clusterizer.main_cluster.to_tree()
        )
        self.assertEqual({}, clusterizer.dependencies)

    def test_user_activation_max_depth_1(self):
        self.script("# script.py\n"
                    "def f(x):\n"
                    "    return x\n"
                    "y = f('1')\n")
        self.clean_execution()

        script = self.evaluation_node(name="script.py")
        var_act = self.evaluation_node(name="f('1')")

        trial = Trial()
        clusterizer = ActivationClusterizer(trial)
        clusterizer.config.max_depth = 1
        clusterizer.run()

        self.assertEqual(
            (script, cluster(script), [var_act]),
            clusterizer.main_cluster.to_tree()
        )
        self.assertEqual({}, clusterizer.dependencies)

    def test_user_activation_no_max_depth(self):
        self.script("# script.py\n"
                    "def f(x):\n"
                    "    return x\n"
                    "y = f('1')\n")
        self.clean_execution()

        script = self.evaluation_node(name="script.py")
        var_act = self.evaluation_node(name="f('1')")

        trial = Trial()
        clusterizer = ActivationClusterizer(trial)
        clusterizer.run()

        self.assertEqual(
            (script, cluster(script), [var_act]),
            clusterizer.main_cluster.to_tree()
        )
        self.assertEqual({}, clusterizer.dependencies)

    def test_file_accesses(self):
        self.script("# script.py\n"
                    "def f(x):\n"
                    "    return g(x)\n"
                    "def g(x):\n"
                    "    return x\n"
                    "y = f('1')\n")
        self.clean_execution()

        script = self.evaluation_node(name="script.py")
        var_act_f = self.evaluation_node(name="f('1')")
        var_act_g = self.evaluation_node(name="g(x)")

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

        clusterizer = ActivationClusterizer(trial)
        clusterizer.run()

        self.assertEqual(
            (script, cluster(script), [
                (var_act_f, cluster(var_act_f), [var_act_g, var_acc2]),
                var_acc1,
            ]),
            clusterizer.main_cluster.to_tree()
        )
        created = clusterizer.created
        self.assertEqual([
            ((created[var_acc1][1], created[var_act_f][1]), ACCESS_ATTR),
            ((created[var_act_g][1], created[var_acc2][1]), ACCESS_ATTR),
            ((created[var_act_f][1], created[var_act_g][1]), REFERENCE_ATTR),
        ], sorted([item for item in viewitems(clusterizer.dependencies)]))

    def test_file_accesses_max_depth_1(self):
        self.script("# script.py\n"
                    "def f(x):\n"
                    "    return g(x)\n"
                    "def g(x):\n"
                    "    return x\n"
                    "y = f('1')\n")
        self.clean_execution()

        script = self.evaluation_node(name="script.py")
        var_act_f = self.evaluation_node(name="f('1')")
        var_act_g = self.evaluation_node(name="g(x)")

        fas = self.metascript.file_accesses_store
        acc1 = fas.add_object(1, "teste", self.metascript.get_time())
        acc1.mode = "w"
        acc1.activation_id = int(var_act_f.split("_")[-1])
        acc2 = fas.add_object(1, "teste2", self.metascript.get_time())
        acc2.mode = "r"
        acc2.activation_id = int(var_act_g.split("_")[-1])
        fas.do_store()

        var_acc1 = "a_{}".format(acc1.id)
        var_acc2 = "a_{}".format(acc2.id)

        trial = Trial()
        clusterizer = ActivationClusterizer(trial)
        clusterizer.config.max_depth = 1
        clusterizer.run()

        self.assertEqual(
            (script, cluster(script), [
                var_act_f, var_acc1, var_acc2,
            ]),
            clusterizer.main_cluster.to_tree()
        )
        created = clusterizer.created
        self.assertEqual([
            ((created[var_acc1][1], created[var_act_f][1]), ACCESS_ATTR),
            ((created[var_act_f][1], created[var_acc2][1]), ACCESS_ATTR),
        ], sorted([item for item in viewitems(clusterizer.dependencies)]))
