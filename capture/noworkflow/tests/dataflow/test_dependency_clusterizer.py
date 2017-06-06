# Copyright (c) 2017 Universidade Federal Fluminense (UFF)
# Copyright (c) 2017 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""Test dataflow clusterizer"""
from __future__ import (absolute_import, print_function,
                        division, unicode_literals)

from future.utils import viewitems

from ...now.persistence.models import Trial
from ...now.models.dependency_graph.attributes import EMPTY_ATTR, ACCESS_ATTR
from ...now.models.dependency_graph.attributes import PROPAGATED_ATTR
from ...now.models.dependency_graph.clusterizer import DependencyClusterizer

from ..collection_testcase import CollectionTestCase


class TestDependencyClusterizer(CollectionTestCase):
    """Test Dataflow Clusterizer"""
    # pylint: disable=missing-docstring
    # pylint: disable=invalid-name
    # pylint: disable=too-many-public-methods

    def test_chain_of_evaluations(self):
        self.script("# script.py\n"
                    "a = 1\n"
                    "b = a\n"
                    "c = b\n")
        self.clean_execution()

        trial = Trial()
        clusterizer = DependencyClusterizer(trial).run()

        self.assertEqual(
            ("e_1", "cluster_1", ["e_2", "e_3", "e_4", "e_5", "e_6", "e_7"]),
            clusterizer.main_cluster.to_tree()
        )
        created = clusterizer.created
        self.assertEqual([
            ((created["e_3"][1], created["e_2"][1]), EMPTY_ATTR),
            ((created["e_4"][1], created["e_3"][1]), EMPTY_ATTR),
            ((created["e_5"][1], created["e_4"][1]), EMPTY_ATTR),
            ((created["e_6"][1], created["e_5"][1]), EMPTY_ATTR),
            ((created["e_7"][1], created["e_6"][1]), EMPTY_ATTR),
        ], sorted([item for item in viewitems(clusterizer.dependencies)]))

    def test_single_activation(self):
        self.script("# script.py\n"
                    "int()\n")
        self.clean_execution()

        trial = Trial()
        clusterizer = DependencyClusterizer(trial).run()

        self.assertEqual(
            ("e_1", "cluster_1", ["e_2"]),
            clusterizer.main_cluster.to_tree()
        )
        self.assertEqual({}, clusterizer.dependencies)

    def test_user_activation_max_depth_1(self):
        self.script("# script.py\n"
                    "def f(x):\n"
                    "    return x\n"
                    "y = f('1')\n")
        self.clean_execution()

        trial = Trial()
        clusterizer = DependencyClusterizer(trial)
        clusterizer.config.max_depth = 1
        clusterizer.run()

        self.assertEqual(
            ("e_1", "cluster_1", ["e_2", "e_3", "e_4", "e_7"]),
            clusterizer.main_cluster.to_tree()
        )
        created = clusterizer.created
        self.assertEqual([
            ((created["e_3"][1], created["e_4"][1]), PROPAGATED_ATTR),
            ((created["e_7"][1], created["e_3"][1]), EMPTY_ATTR),
        ], sorted([item for item in viewitems(clusterizer.dependencies)]))

    def test_user_activation_no_max_depth(self):
        self.script("# script.py\n"
                    "def f(x):\n"
                    "    return x\n"
                    "y = f('1')\n")
        self.clean_execution()

        trial = Trial()
        clusterizer = DependencyClusterizer(trial)
        clusterizer.run()

        self.assertEqual(
            ("e_1", "cluster_1", [
                "e_2", "e_3", "e_4", "e_5", "e_6", "e_7"
            ]),
            clusterizer.main_cluster.to_tree()
        )
        created = clusterizer.created
        self.assertEqual([
            ((created["e_3"][1], created["e_4"][1]), EMPTY_ATTR),
            ((created["e_3"][1], created["e_6"][1]), EMPTY_ATTR),
            ((created["e_5"][1], created["e_4"][1]), EMPTY_ATTR),
            ((created["e_6"][1], created["e_5"][1]), EMPTY_ATTR),
            ((created["e_7"][1], created["e_3"][1]), EMPTY_ATTR),
        ], sorted([item for item in viewitems(clusterizer.dependencies)]))

    def test_file_accesses(self):
        self.script("# script.py\n"
                    "def f(x):\n"
                    "    return g(x)\n"
                    "def g(x):\n"
                    "    return x\n"
                    "y = f('1')\n")
        self.clean_execution()

        acc1 = self.metascript.file_accesses_store.add_object(1, "teste")
        acc1.mode = "w"
        acc1.activation_id = 4
        acc2 = self.metascript.file_accesses_store.add_object(1, "teste2")
        acc2.mode = "r"
        acc2.activation_id = 7
        self.metascript.file_accesses_store.do_store()
        trial = Trial()


        clusterizer = DependencyClusterizer(trial)
        clusterizer.run()

        self.assertEqual(
            ("e_1", "cluster_1", [
                "e_2", "e_3", "e_4", "a_1", "e_5", "e_6", "e_7", "a_2",
                "e_8", "e_9", "e_10", "e_11",
            ]),
            clusterizer.main_cluster.to_tree()
        )
        created = clusterizer.created
        self.assertEqual([
            ((created["a_1"][1], created["e_4"][1]), ACCESS_ATTR),
            ((created["e_10"][1], created["e_9"][1]), EMPTY_ATTR),
            ((created["e_11"][1], created["e_4"][1]), EMPTY_ATTR),
            ((created["e_4"][1], created["e_5"][1]), EMPTY_ATTR),
            ((created["e_4"][1], created["e_7"][1]), EMPTY_ATTR),
            ((created["e_6"][1], created["e_5"][1]), EMPTY_ATTR),
            ((created["e_7"][1], created["a_2"][1]), ACCESS_ATTR),
            ((created["e_7"][1], created["e_10"][1]), EMPTY_ATTR),
            ((created["e_7"][1], created["e_8"][1]), EMPTY_ATTR),
            ((created["e_8"][1], created["e_6"][1]), EMPTY_ATTR),
            ((created["e_9"][1], created["e_8"][1]), EMPTY_ATTR),
        ], sorted([item for item in viewitems(clusterizer.dependencies)]))

    def test_file_accesses_max_depth_2(self):
        self.script("# script.py\n"
                    "def f(x):\n"
                    "    return g(x)\n"
                    "def g(x):\n"
                    "    return x\n"
                    "y = f('1')\n")
        self.clean_execution()

        acc1 = self.metascript.file_accesses_store.add_object(1, "teste")
        acc1.mode = "w"
        acc1.activation_id = 4
        acc2 = self.metascript.file_accesses_store.add_object(1, "teste2")
        acc2.mode = "r"
        acc2.activation_id = 7
        self.metascript.file_accesses_store.do_store()
        trial = Trial()


        clusterizer = DependencyClusterizer(trial)
        clusterizer.config.max_depth = 2
        clusterizer.run()

        self.assertEqual(
            ("e_1", "cluster_1", [
                "e_2", "e_3", "e_4", "e_6", "e_7", "a_2", "e_8", "a_1", "e_5",
                "e_11"
            ]),
            clusterizer.main_cluster.to_tree()
        )
        created = clusterizer.created
        self.assertEqual([
            ((created["a_1"][1], created["e_4"][1]), ACCESS_ATTR),
            ((created["e_11"][1], created["e_4"][1]), EMPTY_ATTR),
            ((created["e_4"][1], created["e_5"][1]), EMPTY_ATTR),
            ((created["e_4"][1], created["e_7"][1]), EMPTY_ATTR),
            ((created["e_6"][1], created["e_5"][1]), EMPTY_ATTR),
            ((created["e_7"][1], created["a_2"][1]), ACCESS_ATTR),
            ((created["e_7"][1], created["e_8"][1]), PROPAGATED_ATTR),
            ((created["e_8"][1], created["e_6"][1]), EMPTY_ATTR),
        ], sorted([item for item in viewitems(clusterizer.dependencies)]))

    def test_file_accesses_max_depth_1(self):
        self.script("# script.py\n"
                    "def f(x):\n"
                    "    return g(x)\n"
                    "def g(x):\n"
                    "    return x\n"
                    "y = f('1')\n")
        self.clean_execution()

        acc1 = self.metascript.file_accesses_store.add_object(1, "teste")
        acc1.mode = "w"
        acc1.activation_id = 4
        acc2 = self.metascript.file_accesses_store.add_object(1, "teste2")
        acc2.mode = "r"
        acc2.activation_id = 7
        self.metascript.file_accesses_store.do_store()
        trial = Trial()

        clusterizer = DependencyClusterizer(trial)
        clusterizer.config.max_depth = 1
        clusterizer.run()

        self.assertEqual(
            ("e_1", "cluster_1", [
                "e_2", "e_3", "e_4",
                "a_1", "a_2", "e_5", "e_11"
            ]),
            clusterizer.main_cluster.to_tree()
        )
        created = clusterizer.created
        self.assertEqual([
            ((created["a_1"][1], created["e_4"][1]), ACCESS_ATTR),
            ((created["e_11"][1], created["e_4"][1]), EMPTY_ATTR),
            ((created["e_4"][1], created["a_2"][1]), ACCESS_ATTR),
            ((created["e_4"][1], created["e_5"][1]), PROPAGATED_ATTR),
        ], sorted([item for item in viewitems(clusterizer.dependencies)]))

    def test_user_activation_rank_lines(self):
        self.script("# script.py\n"
                    "def f(x):\n"
                    "    return x + x\n"
                    "y = f('1') + '1'\n")
        self.clean_execution()

        trial = Trial()
        clusterizer = DependencyClusterizer(trial)
        clusterizer.config.rank_option = 1
        clusterizer.run()

        self.assertEqual(
            ("e_1", "cluster_1", [
                "e_2", "e_3", "e_4", "e_5", "e_6", "e_7", "e_8",
                "e_9", "e_10", "e_11"
            ]),
            clusterizer.main_cluster.to_tree()
        )
        created = clusterizer.created
        self.assertEqual([
            ((created["e_10"][1], created["e_3"][1]), EMPTY_ATTR),
            ((created["e_10"][1], created["e_9"][1]), EMPTY_ATTR),
            ((created["e_11"][1], created["e_10"][1]), EMPTY_ATTR),
            ((created["e_3"][1], created["e_4"][1]), EMPTY_ATTR),
            ((created["e_3"][1], created["e_8"][1]), EMPTY_ATTR),
            ((created["e_5"][1], created["e_4"][1]), EMPTY_ATTR),
            ((created["e_6"][1], created["e_5"][1]), EMPTY_ATTR),
            ((created["e_7"][1], created["e_5"][1]), EMPTY_ATTR),
            ((created["e_8"][1], created["e_6"][1]), EMPTY_ATTR),
            ((created["e_8"][1], created["e_7"][1]), EMPTY_ATTR),
        ], sorted([item for item in viewitems(clusterizer.dependencies)]))

        ranks = sorted([
            sorted(x) for x in created["e_1"][1].ranks
        ])

        self.assertEqual([
            created["e_10"][1], created["e_11"][1],
            created["e_3"][1], created["e_4"][1], created["e_9"][1],
        ], ranks[0])
        self.assertEqual([
            created["e_2"][1], created["e_5"][1]
        ], ranks[1])
        self.assertEqual([
            created["e_6"][1], created["e_7"][1], created["e_8"][1],
        ], ranks[2])
