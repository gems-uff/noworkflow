# Copyright (c) 2016 Universidade Federal Fluminense (UFF)
# Copyright (c) 2016 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""Prospective Provenance Analyzer"""
from __future__ import (absolute_import, print_function,
                        division, unicode_literals)

from collections import defaultdict
from .modules.data.experiment_collector import ExperimentDataCollector
from ...persistence import relational


class ProspectiveAnalyzer:
    """Main analyzer for prospective provenance"""

    def __init__(self, trial_id, session=None):
        self.trial_id = trial_id
        self.session = session or relational.session
        self.collector = ExperimentDataCollector(trial_id, self.session)

    def analyze(self, filter_type='everything', **options):
        """Generate prospective provenance"""
        if not self.collector.trial_check:
            raise ValueError(f"Trial {self.trial_id} not found")

        config = self._build_config(filter_type, **options)

        if filter_type == 'function':
            components = self.collector.code_function(config)
        else:
            components = self.collector.code_components(config)

        if not components:
            raise ValueError("No code components found. Check filter parameters.")

        result = {
            'trial_id': self.trial_id,
            'filter_type': filter_type,
            'components': components
        }

        if options.get('activations'):
            result['activations'] = self.collector.activation_line(config)

        if options.get('checkpoints'):
            result['checkpoints'] = self.collector.runtime_line(config)

        if options.get('contents'):
            result['contents'] = self.collector.variables_content(config)

        return result

    def _build_config(self, filter_type, **options):
        """Build configuration dictionary for queries"""
        config = defaultdict(list)
        config['trial_id'].append(self.trial_id)
        config['filter_type'].append(filter_type)
        config['activations_v'].append(options.get('activations', False))
        config['checkpoints_v'].append(options.get('checkpoints', False))
        config['contents_v'].append(options.get('contents', False))
        config['indented'].append(options.get('indented', False))

        if filter_type == 'lines':
            config['start'].append(options.get('start_line', 0))
            config['final'].append(options.get('end_line', 0))
        elif filter_type == 'partial':
            config['start'].append(options.get('start_line', 0))
        elif filter_type == 'function':
            config['def_name'].append(options.get('function_name'))

        return config

    def get_function_definitions(self):
        """Get all function definitions in the trial"""
        return self.collector.return_def

    def get_function_calls(self):
        """Get all function calls in the trial"""
        return self.collector.return_calls

    def generate_graph(self, **options):
        """Generate full prospective provenance control-flow graph

        Args:
            **options: Optional configuration
                - activations: Include execution activations
                - checkpoints: Include execution timing
                - contents: Include variable contents
                - indented: Show indentation levels

        Returns:
            Graphviz Digraph object with complete control-flow graph
        """
        from .modules.provenance.definition import DefinitionProvenanceAnalyzer

        if not self.collector.trial_check:
            raise ValueError(f"Trial {self.trial_id} not found")

        config = self._build_config('everything', **options)
        components = self.collector.code_components(config)

        if not components:
            raise ValueError("No code components found")

        analyzer = DefinitionProvenanceAnalyzer(self.trial_id)
        analyzer.component_analyzer(self.collector, components, config)

        return analyzer.provenance
