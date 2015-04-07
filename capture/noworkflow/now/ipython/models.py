# Copyright (c) 2015 Universidade Federal Fluminense (UFF)
# Copyright (c) 2015 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.

from __future__ import (absolute_import, print_function,
                        division, unicode_literals)


from ..models import Trial, Diff, History, Model, TrialProlog


models = {
    'History': [History],
    'Trial': [Trial],
    'Diff': [Diff],
    '*': [History, Trial, Diff],
}


def update_all(attribute, value, model='*'):
    for cls in models[model]:
        for instance in cls.get_instances():
            setattr(instance, attribute, value)


def set_default(attribute, value, all=False, model='*'):
    for cls in models[model]:
        if attribute in cls.DEFAULT:
            cls.DEFAULT[attribute] = value

    if all:
        update_all(attribute, value, model=model)
