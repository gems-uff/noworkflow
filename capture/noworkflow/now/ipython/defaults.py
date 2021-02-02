# Copyright (c) 2021 Universidade Federal Fluminense (UFF)
# Copyright (c) 2021 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.

from ..persistence.models import MetaModel

def set_default(key, value, model="*"):
    """Set a default metamodel value"""
    if isinstance(value, str) and value.isdigit():
        value = int(value)
    MetaModel.set_classes_default(key, value, model=model)
