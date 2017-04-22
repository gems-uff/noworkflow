# Copyright (c) 2016 Universidade Federal Fluminense (UFF)
# Copyright (c) 2016 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
""" Define helper functions for collection """

from future.utils import viewvalues
from ..persistence.models.compartment import Compartment
from ..persistence.models.evaluation import Evaluation

def get_compartment(metascript, whole_id, name):
    """Get compartment by whole_id and name"""
    store = metascript.compartments_store
    for compartment_id in reversed(store.order):
        compartment = store.store.get(compartment_id, None)
        if compartment is None:
            continue
        if compartment.whole_id == whole_id and compartment.name == name:
            return compartment.part_id
    return Compartment.find_part_id(metascript.trial_id, whole_id, name)

def last_evaluation_by_value_id(metascript, value_id):
    """Get evaluation by value_id"""
    store = metascript.evaluations_store
    for evaluation_id in reversed(store.order):
        evaluation = store.store.get(evaluation_id, None)
        if evaluation is None:
            continue
        if evaluation.value_id == value_id:
            return (
                evaluation.activation_id,
                evaluation.id,
                evaluation.code_component_id
            )
    return Evaluation.find_by_value_id(
        metascript.trial_id, value_id, order="desc"
    )
