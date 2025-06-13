# Copyright (c) 2016 Universidade Federal Fluminense (UFF)
# Copyright (c) 2016 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""Lightweight Trial"""
from __future__ import (absolute_import, print_function,
                        division, unicode_literals)

from ..models import Trial
from .. import content

from .base import BaseLW, define_attrs


class TrialLW(BaseLW):
    """Trial lightweight object"""

    __slots__, attributes = define_attrs(
        ["id", "script", "start", "finish", "command",
        "path","status","modules_inherited_from_trial_id","parent_id","main_id","experiment_id","user_id"]
    )
    nullable = set()
    model = Trial

    def __init__(self, id_, script, start, finish, command,path,status,modules_inherited_from_trial_id,parent_id,main_id,experiment_id=None,user_id=None):
        # pylint: disable=too-many-arguments
        self.id = id_
        self.trial_id = id_
        self.script = script  # pylint: disable=invalid-name
        self.start = start
        self.finish = finish
        self.command = command
        self.path = path
        self.status = status
        self.modules_inherited_from_trial_id = modules_inherited_from_trial_id
        self.parent_id = parent_id
        self.main_id = main_id
        self.experiment=experiment_id
        self.user_id=user_id

    def is_complete(self):
        """The first TrialLW cannot be removed from object store"""
        return self.id != 1

    def __repr__(self):
        return ("TrialLW(id={0.id})").format(self)

    def __json__(self):
        finish=None
        if  self.finish is not None:
            finish=self.finish.strftime('%Y-%m-%d %H:%M:%S.%f')
        return {
            'trial_id': self.trial_id,
            'id': self.id,
            'script': self.script,
            'start': self.start.strftime('%Y-%m-%d %H:%M:%S.%f'),
            'finish': finish,
            'command': self.command,
            'path': self.path,
            'status': self.status,
            'modules_inherited_from_trial_id': self.modules_inherited_from_trial_id,
            'parent_id': self.parent_id,
            'main_id': self.main_id,
            'experiment_id': self.experiment,
            'user_id': self.user_id,
        }
