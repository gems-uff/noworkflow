# Copyright (c) 2017 Universidade Federal Fluminense (UFF)
# Copyright (c) 2017 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""Pattern Matching Module"""
# pylint: disable=invalid-name, redefined-builtin

from .access_rules import (
    access_id,
    file_read,
    file_read_id,
    file_written,
    file_written_id,
)
from .activation_rules import (
    activation_id,
    called_activation_id,
    evaluation_line_id,
    filter_activation_ids,
    is_activation_id,
    map_evaluation_code_ids,
    map_evaluation_lines_id,
    recursive_internal_evaluations_ids,
)
from .code_rules import code_line_id, map_code_lines_id
from .docstring_rules import (
    activation_docstring_id,
    code_docstring_id,
    docstring,
    docstring_id,
)
from .hash_rules import changed, changed_id, hash, hash_id
from .helpers import between, member, once
from .id_rules import evaluation_code_id
from .mode_access_rules import (
    access_mode_id,
    code_mode_id,
    delete_mode,
    mode,
    mode_id,
    param_mode,
    read_mode,
    write_mode,
)
from .name_rules import (
    access_name,
    activation_name,
    code_name,
    evaluation_name,
    map_names,
    name,
)
from .scope_rules import code_scope_id, evaluation_scope_id, scope, scope_id
from .temporal_inference_rules import (
    access_influence,
    access_influence_id,
    access_stack,
    access_stack_id,
    activation_stack,
    activation_stack_id,
    indirect_access,
    indirect_access_id,
    indirect_activation,
    indirect_activation_id,
    temporal_activation_influence,
    temporal_activation_influence_id,
)
from .timestamp_rules import (
    duration,
    duration_id,
    successor,
    successor_id,
    timestamp,
    timestamp_id,
)
