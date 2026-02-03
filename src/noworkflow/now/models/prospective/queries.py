# Copyright (c) 2016 Universidade Federal Fluminense (UFF)
# Copyright (c) 2016 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""Prospective Provenance Queries"""
from __future__ import (absolute_import, print_function,
                        division, unicode_literals)

from ...persistence import relational
from ...persistence.models.code_component import CodeComponent
from ...persistence.models.evaluation import Evaluation


class ProspectiveQueries:
    """Query builder for prospective provenance data"""

    def __init__(self, trial_id, session=None):
        self.trial_id = trial_id
        self.session = session or relational.session

    def list_all_codes(self):
        """Get all code components for the trial ordered by line number"""
        return (
            self.session.query(CodeComponent.m)
            .filter(
                (CodeComponent.m.trial_id == self.trial_id) &
                (CodeComponent.m.first_char_line != -1)
            )
            .order_by(
                CodeComponent.m.first_char_line,
                CodeComponent.m.first_char_column
            )
        )

    def list_lines_codes(self, start_line, end_line):
        """Get code components within a line range"""
        return (
            self.session.query(CodeComponent.m)
            .filter(
                (CodeComponent.m.trial_id == self.trial_id) &
                (CodeComponent.m.first_char_line >= start_line) &
                (CodeComponent.m.last_char_line <= end_line)
            )
            .order_by(
                CodeComponent.m.first_char_line,
                CodeComponent.m.first_char_column
            )
        )

    def list_partial_codes(self, start_line):
        """Get code components from a start line onwards"""
        return (
            self.session.query(CodeComponent.m)
            .filter(
                (CodeComponent.m.trial_id == self.trial_id) &
                (CodeComponent.m.first_char_line >= start_line)
            )
            .order_by(
                CodeComponent.m.first_char_line,
                CodeComponent.m.first_char_column
            )
        )

    def get_all_function_defs(self):
        """Get all function definitions"""
        return (
            self.session.query(CodeComponent.m)
            .filter(
                (CodeComponent.m.trial_id == self.trial_id) &
                (CodeComponent.m.type == 'function_def')
            )
            .order_by(CodeComponent.m.first_char_line)
        )

    def get_all_calls(self):
        """Get all function calls"""
        return (
            self.session.query(CodeComponent.m)
            .filter(
                (CodeComponent.m.trial_id == self.trial_id) &
                (CodeComponent.m.type == 'call')
            )
            .order_by(CodeComponent.m.first_char_line)
        )

    def get_function_by_name(self, function_name):
        """Get a specific function definition by name"""
        return (
            self.session.query(CodeComponent.m)
            .filter(
                (CodeComponent.m.trial_id == self.trial_id) &
                (CodeComponent.m.name == function_name) &
                (CodeComponent.m.type == 'function_def')
            )
            .order_by(CodeComponent.m.first_char_line)
        )

    def get_function_components(self, function_name):
        """Get all components within a function"""
        func_def = self.get_function_by_name(function_name).first()
        if not func_def:
            return self.session.query(CodeComponent.m).filter(False)

        return self.list_lines_codes(
            func_def.first_char_line,
            func_def.last_char_line
        )

    def get_arguments(self, line_number):
        """Get function arguments at a specific line"""
        return (
            self.session.query(CodeComponent.m)
            .filter(
                (CodeComponent.m.trial_id == self.trial_id) &
                (CodeComponent.m.first_char_line == line_number) &
                (CodeComponent.m.type == 'arguments')
            )
        )

    def get_else_components(self, start_line, end_line):
        """Get else clause components in a range"""
        return (
            self.session.query(CodeComponent.m)
            .filter(
                (CodeComponent.m.trial_id == self.trial_id) &
                (CodeComponent.m.type == 'syntax') &
                (CodeComponent.m.name == 'else:') &
                (CodeComponent.m.first_char_line >= start_line) &
                (CodeComponent.m.last_char_line <= end_line)
            )
        )

    def get_activations(self):
        """Get execution activations with timestamps"""
        return (
            self.session.query(
                CodeComponent.m.first_char_line,
                Evaluation.m.checkpoint
            )
            .join(
                Evaluation.m,
                (Evaluation.m.code_component_id == CodeComponent.m.id) &
                (Evaluation.m.trial_id == CodeComponent.m.trial_id)
            )
            .filter(
                (CodeComponent.m.trial_id == self.trial_id) &
                (CodeComponent.m.first_char_line != -1)
            )
            .order_by(CodeComponent.m.first_char_line)
        )

    def get_variable_contents(self):
        """Get variable contents from evaluations"""
        return (
            self.session.query(
                CodeComponent.m.first_char_line,
                Evaluation.m.repr,
                CodeComponent.m.name,
                CodeComponent.m.first_char_column
            )
            .join(
                Evaluation.m,
                (Evaluation.m.code_component_id == CodeComponent.m.id) &
                (Evaluation.m.trial_id == CodeComponent.m.trial_id)
            )
            .filter(
                (CodeComponent.m.trial_id == self.trial_id) &
                (CodeComponent.m.first_char_line != -1) &
                (CodeComponent.m.type == 'name')
            )
            .order_by(CodeComponent.m.first_char_line)
        )


def get_all_components(trial_id, session=None):
    """Get all code components for a trial"""
    queries = ProspectiveQueries(trial_id, session)
    return queries.list_all_codes().all()


def get_function_definitions(trial_id, session=None):
    """Get all function definitions for a trial"""
    queries = ProspectiveQueries(trial_id, session)
    return queries.get_all_function_defs().all()


def get_function_calls(trial_id, session=None):
    """Get all function calls for a trial"""
    queries = ProspectiveQueries(trial_id, session)
    return queries.get_all_calls().all()
