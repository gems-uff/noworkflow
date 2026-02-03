# Copyright (c) 2016 Universidade Federal Fluminense (UFF)
# Copyright (c) 2016 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""Generate Prospective Provenance in DOT Format"""
from __future__ import (absolute_import, print_function,
                        division, unicode_literals)

from collections import defaultdict
from .modules.provenance.definition import DefinitionProvenanceAnalyzer
from .modules.data.experiment_collector import ExperimentDataCollector
from ...persistence import relational


def generate_prospective_prov(trial):
    """Generate prospective provenance as Graphviz DOT format

    Creates a complete control-flow graph with:
    - IF/ELSE branching with True/False labels
    - Loop back-edges and "End Loop" labels
    - Function call → definition edges (dashed)
    - Function clustering (dashed subgraph borders)
    - Exception handling flow

    Args:
        trial: Trial object with .id attribute

    Returns:
        String containing DOT format graph
    """
    trial_id = trial.id
    session = relational.session
    collector = ExperimentDataCollector(trial_id, session)

    if not collector.trial_check:
        raise ValueError(f"Trial {trial_id} not found")

    config = defaultdict(list)
    config['trial_id'].append(trial_id)
    config['filter_type'].append('everything')
    config['activations_v'].append(False)
    config['checkpoints_v'].append(False)
    config['contents_v'].append(False)
    config['indented'].append(False)

    components = collector.code_components(config)

    if not components:
        raise ValueError("No code components found")

    analyzer = DefinitionProvenanceAnalyzer(trial_id)
    analyzer.component_analyzer(collector, components, config)

    return analyzer.provenance.source
