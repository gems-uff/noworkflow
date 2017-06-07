# Copyright (c) 2017 Universidade Federal Fluminense (UFF)
# Copyright (c) 2017 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""Test clusterizer configuration"""

from __future__ import (absolute_import, print_function,
                        division, unicode_literals)

from ...now.models.dependency_graph.config import DependencyConfig
from ...now.models.dependency_graph.clusterizer import Clusterizer
from ...now.models.dependency_graph.clusterizer import ActivationClusterizer
from ...now.models.dependency_graph.clusterizer import DependencyClusterizer
from ...now.models.dependency_graph.clusterizer import ProspectiveClusterizer
from ...now.models.dependency_graph.filters import FilterValuesOut
from ...now.models.dependency_graph.filters import FilterAccessesOut
from ...now.models.dependency_graph.filters import FilterExternalAccessesOut
from ...now.models.dependency_graph.filters import FilterInternalsOut
from ...now.models.dependency_graph.filters import AcceptAllNodesFilter
from ...now.models.dependency_graph.filters import JoinedFilter
from ...now.models.dependency_graph.synonymers import Synonymer
from ...now.models.dependency_graph.synonymers import AccessNameSynonymer
from ...now.models.dependency_graph.synonymers import SameSynonymer
from ...now.models.dependency_graph.synonymers import ValueSynonymer
from ...now.models.dependency_graph.synonymers import JoinedSynonymer

from ..collection_testcase import CollectionTestCase


class TrialMock(object):
    """Mock trial"""
    # pylint: disable=too-few-public-methods
    initial_activation = None


class TestClusterizerConfig(CollectionTestCase):
    """Test Clusterizer Configuration"""
    # pylint: disable=missing-docstring
    # pylint: disable=invalid-name
    # pylint: disable=too-many-public-methods

    def test_default_filter_hide_values_show_accesses_hide_internals(self):
        # pylint: disable=protected-access
        config = DependencyConfig()
        filter_ = config.filter()
        self.assertEqual(JoinedFilter, type(filter_))
        self.assertEqual(FilterValuesOut, type(filter_._filters[0]))
        self.assertEqual(FilterExternalAccessesOut, type(filter_._filters[1]))
        self.assertEqual(FilterInternalsOut, type(filter_._filters[2]))

    def test_filter_show_values_show_accesses_hide_internals(self):
        # pylint: disable=protected-access
        config = DependencyConfig()
        config.show_values = True
        config.show_external_files = True
        filter_ = config.filter()
        self.assertEqual(FilterInternalsOut, type(filter_))

    def test_filter_show_values_hide_accesses_hide_internals(self):
        # pylint: disable=protected-access
        config = DependencyConfig()
        config.show_values = True
        config.show_accesses = False
        config.show_external_files = True
        filter_ = config.filter()
        self.assertEqual(JoinedFilter, type(filter_))
        self.assertEqual(FilterAccessesOut, type(filter_._filters[0]))
        self.assertEqual(FilterInternalsOut, type(filter_._filters[1]))

    def test_filter_hide_values_hide_accesses_hide_internals(self):
        # pylint: disable=protected-access
        config = DependencyConfig()
        config.show_accesses = False
        config.show_external_files = True
        filter_ = config.filter()
        self.assertEqual(JoinedFilter, type(filter_))
        self.assertEqual(FilterValuesOut, type(filter_._filters[0]))
        self.assertEqual(FilterAccessesOut, type(filter_._filters[1]))
        self.assertEqual(FilterInternalsOut, type(filter_._filters[2]))

    def test_filter_show_values_show_accesses_show_internals(self):
        config = DependencyConfig()
        config.show_values = True
        config.show_internals = True
        config.show_external_files = True
        self.assertEqual(AcceptAllNodesFilter, type(config.filter()))

    def test_filter_hide_external_accesses(self):
        config = DependencyConfig()
        config.show_values = True
        config.show_internals = True
        config.show_external_files = False
        self.assertEqual(FilterExternalAccessesOut, type(config.filter()))

    def test_filter_extra(self):
        config = DependencyConfig()
        config.show_values = True
        config.show_internals = True
        config.show_external_files = True
        self.assertEqual(
            FilterExternalAccessesOut,
            type(config.filter([FilterExternalAccessesOut()]))
        )

    def test_default_synonymer_combine_accesses(self):
        config = DependencyConfig()
        synonymer = config.synonymer()
        self.assertEqual(JoinedSynonymer, type(synonymer))
        self.assertEqual(AccessNameSynonymer, type(synonymer.synonymers[0]))
        self.assertEqual(SameSynonymer, type(synonymer.synonymers[1]))

    def test_synonymer_does_not_combine_accesses(self):
        config = DependencyConfig()
        config.combine_accesses = False
        self.assertEqual(SameSynonymer, type(config.synonymer()))

    def test_synonymer_does_not_combine_accesses_nor_assigments(self):
        config = DependencyConfig()
        config.combine_accesses = False
        config.combine_assignments = False
        self.assertEqual(Synonymer, type(config.synonymer()))

    def test_synonymer_combines_values(self):
        config = DependencyConfig()
        config.combine_assignments = False
        config.combine_values = True
        synonymer = config.synonymer()
        self.assertEqual(JoinedSynonymer, type(synonymer))
        self.assertEqual(AccessNameSynonymer, type(synonymer.synonymers[0]))
        self.assertEqual(ValueSynonymer, type(synonymer.synonymers[1]))

    def test_synonymer_extra(self):
        config = DependencyConfig()
        config.combine_accesses = False
        config.combine_assignments = False
        self.assertEqual(
            SameSynonymer,
            type(config.synonymer([SameSynonymer()]))
        )

    def test_mode_simulation(self):
        config = DependencyConfig()
        config.mode = "simulation"
        self.assertEqual(
            Clusterizer,
            type(config.clusterizer(TrialMock()))
        )

    def test_mode_activation(self):
        config = DependencyConfig()
        config.mode = "activation"
        self.assertEqual(
            ActivationClusterizer,
            type(config.clusterizer(TrialMock()))
        )

    def test_mode_dependency(self):
        config = DependencyConfig()
        config.mode = "dependency"
        self.assertEqual(
            DependencyClusterizer,
            type(config.clusterizer(TrialMock()))
        )

    def test_mode_prospective(self):
        config = DependencyConfig()
        config.mode = "prospective"
        self.assertEqual(
            ProspectiveClusterizer,
            type(config.clusterizer(TrialMock()))
        )
