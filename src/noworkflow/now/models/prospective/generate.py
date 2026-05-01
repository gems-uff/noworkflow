# Copyright (c) 2016 Universidade Federal Fluminense (UFF)
# Copyright (c) 2016 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""Generate Prospective Provenance in DOT Format"""
from __future__ import (absolute_import, print_function,
                        division, unicode_literals)

from collections import defaultdict
from .modules.provenance.definition import DefinitionProvenanceAnalyzer

from ...persistence import relational
from ...persistence.models import Trial


def generate_prospective_prov(trial: Trial):
    """Generate prospective provenance as Graphviz DOT format

    Args:
        trial: Trial object with .id attribute

    Returns:
        String containing DOT format graph
    """
    if trial.id == None:
        raise ValueError(f"Error loading trial: {e}")

    analyzer = DefinitionProvenanceAnalyzer(trial.id)
    analyzer.component_analyzer()

    return analyzer.provenance.source
