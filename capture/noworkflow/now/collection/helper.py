# Copyright (c) 2016 Universidade Federal Fluminense (UFF)
# Copyright (c) 2016 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
""" Define helper functions for collection """

from future.utils import viewvalues
from ..persistence.models.compartment import Compartment

def get_compartment(metascript, whole_id, name):
    """Get compartment by whole_id and name"""
    for compartment in viewvalues(metascript.compartments_store.store):
        if compartment.whole_id == whole_id and compartment.name == name:
            return compartment.part_id
    return Compartment.find_part_id(metascript.trial_id, whole_id, name)
