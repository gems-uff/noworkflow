# Copyright (c) 2017 Universidade Federal Fluminense (UFF)
# Copyright (c) 2017 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""Pattern Matching Module"""
# pylint: disable=invalid-name, redefined-builtin


from .helpers import between, once, member
from .id_rules import compartment_id, evaluation_code_id
from .name_rules import code_name, evaluation_name, activation_name, access_name
from .name_rules import value_name, compartment_name, name, map_names
from .timestamp_rules import timestamp_id, duration_id, successor_id
from .timestamp_rules import timestamp, duration, successor
from .mode_access_rules import read_mode, write_mode, delete_mode, param_mode
from .mode_access_rules import access_mode_id, code_mode_id, mode_id, mode
from .hash_rules import hash_id, changed_id, hash, changed
from .code_rules import code_line_id, map_code_lines_id
from .activation_rules import is_activation_id, activation_id
from .activation_rules import called_activation_id, evaluation_line_id
from .activation_rules import map_evaluation_lines_id, map_evaluation_code_ids
from .activation_rules import filter_activation_ids
from .activation_rules import recursive_internal_evaluations_ids
from .docstring_rules import code_docstring_id, activation_docstring_id
from .docstring_rules import docstring_id, docstring
from .scope_rules import code_scope_id, evaluation_scope_id, scope_id, scope
from .access_rules import file_read_id, file_written_id, access_id
from .access_rules import file_read, file_written
from .temporal_inference_rules import activation_stack_id, activation_stack
from .temporal_inference_rules import indirect_activation_id
from .temporal_inference_rules import indirect_activation
from .temporal_inference_rules import temporal_activation_influence_id
from .temporal_inference_rules import temporal_activation_influence
from .temporal_inference_rules import access_stack_id, access_stack
from .temporal_inference_rules import indirect_access_id, indirect_access
from .temporal_inference_rules import access_influence_id, access_influence
