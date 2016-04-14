# Copyright (c) 2015 Universidade Federal Fluminense (UFF)
# Copyright (c) 2015 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""Models Scenarios"""


from ...now.persistence.models import Trial
from ..helpers.models import erase_db, new_trial, trial_list
from ..helpers.models import block_params, component_params, evaluation_params
from ..helpers.models import activation_params


class Definition(object):
    """Create a scenario.

    Step1 (create_component):
    - Trial t:
        status = "finished"
        [trial_id = t.id]
        [activation_id = t.main_activation.id]
        [trial = t]
    - CodeComponent cc:
        trial_id = t.id
        name = "function"
        type = "function_def"
        mode = "w"
        first_char_line = 1
        first_char_column = 0
        last_char_line = 2
        last_char_column = 8
        container_id = t.main_id
        [id = cc.id]
        [pk = t.id, cc.id]
    - Evaluation e1:
        trial_id = t.id
        code_component_id = cc.id
        activation_id = t.main_activation.id
        minute = 40
        [eval_id1 = e1.id]
    - Evaluation e2:
        trial_id = t.id
        code_component_id = cc.id
        activation_id = t.main_activation.id
        minute = 41
        [eval_id2 = e2.id]

    Step2 (create_block):
    - CodeBlock:
        trial_id = cc.trial_id
        id = cc.id
        code = "def function()\n    'ab'"
        docstring = "ab"

    Step3 (create_subcomponents)
    - CodeComponent cc2:
        trial_id = t.id
        type = "call"
        container_id = t.main_id
    - CodeComponent:
        trial_id = t.id
        container_id = cc.id
    - CodeComponent:
        trial_id = t.id
        container_id = cc.id
    - Evaluation e3:
        trial_id = t.id
        code_component_id = cc.id
        activation_id = t.main_activation.id
    - Activation a3:
        trial_id = t.id
        id = e3.id
        code_block_id = cc.id

    """

    def __init__(self, step=0):
        self.id = self.trial_id = self.pk = None                                 # pylint: disable=invalid-name
        self.eval_id1 = self.eval_id2 = None
        self.trial = self.activation_id = None
        for _, step_method in zip(range(1, step + 1), self.steps):
            step_method(self)

    def create_component(self):
        """Create a code component and two associated evaluations"""
        erase_db()
        self.trial_id = new_trial(status="finished")
        self.trial = Trial(self.trial_id)
        meta = trial_list[self.trial_id]

        self.id = meta.code_components_store.add(*component_params(
            name="function", type_="function_def", mode="w",
            first_char_line=1, first_char_column=0,
            last_char_line=2, last_char_column=8,
            container_id=self.trial.main_id))
        activation = list(self.trial.activations)[0]
        self.activation_id = activation.id
        self.eval_id1 = meta.evaluations_store.add(*evaluation_params(
            self.id, activation.id, minute=40
        ))
        self.eval_id2 = meta.evaluations_store.add(*evaluation_params(
            self.id, activation.id, minute=41
        ))
        meta.code_components_store.fast_store(self.trial_id)
        meta.evaluations_store.fast_store(self.trial_id)

        self.pk = (self.trial_id, self.id)

    def create_block(self):
        """Create a corresponding code_block"""
        meta = trial_list[self.trial_id]
        meta.code_blocks_store.add(*block_params(
            self.id, code="def function()\n    'ab'", docstring="ab"
        ))
        meta.code_blocks_store.fast_store(self.trial_id)

    def create_subcomponents(self):
        """Create subcomponents and activation"""
        meta = trial_list[self.trial_id]
        meta.code_components_store.add(*component_params(container_id=self.id))
        meta.code_components_store.add(*component_params(container_id=self.id))
        cc2 = meta.code_components_store.add(*component_params(
            type_="call", container_id=self.trial.main_id
        ))
        eid = meta.evaluations_store.add(*evaluation_params(
            code_component_id=cc2, activation_id=self.activation_id
        ))
        meta.activations_store.add(*activation_params(
            eid, self.id
        ))
        meta.code_components_store.fast_store(self.trial_id)
        meta.evaluations_store.fast_store(self.trial_id)
        meta.activations_store.fast_store(self.trial_id)

    steps = [create_component, create_block, create_subcomponents]



