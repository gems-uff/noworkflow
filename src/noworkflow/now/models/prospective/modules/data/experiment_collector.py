# Copyright (c) 2016 Universidade Federal Fluminense (UFF)
# Copyright (c) 2016 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""Experiment Data Collector for Prospective Provenance"""
from __future__ import (absolute_import, print_function,
                        division, unicode_literals)

from ...queries import ProspectiveQueries
from .....persistence.models import Trial
from .....persistence import relational


class ExperimentDataCollector:
    """Data collector interface for prospective provenance"""

    def __init__(self, trial_id, session=None):
        self.trial_id = trial_id
        self.session = session or relational.session
        self.queries = ProspectiveQueries(trial_id, self.session)

    @property
    def trial_check(self):
        """Check if trial exists"""
        try:
            trial = Trial(trial_ref=self.trial_id)
            # Check if trial exists - prospective provenance is about script structure,
            # so we don't require the trial to be "finished"
            if trial.id:
                return True
            else:
                print(f"Trial {self.trial_id} not found")
                return False
        except Exception as e:
            print(f"Error loading trial {self.trial_id}: {e}")
            print("Something is wrong! Maybe the trial is not available in noWorkflow!")
            print("Try running the trial again in noWorkflow!")
            return False

    def code_components(self, config):
        """Get code components based on filter type"""
        filter_type = config.get('filter_type', ['everything'])[0]

        if filter_type == 'lines':
            start_line = config.get('start', [0])[0]
            end_line = config.get('final', [0])[0]
            query = self.queries.list_lines_codes(start_line, end_line)
        elif filter_type == 'partial':
            start_line = config.get('start', [0])[0]
            query = self.queries.list_partial_codes(start_line)
        else:
            query = self.queries.list_all_codes()

        results = query.all()
        if results:
            return [
                (comp.first_char_line, comp.last_char_line, comp.type,
                 comp.name, comp.first_char_column)
                for comp in results
            ]
        else:
            print("Something went wrong in the trial verification!")
            return None

    def code_function(self, config):
        """Get code components for a specific function"""
        function_name = config.get('def_name', [None])[0]
        if not function_name:
            return False

        func_def = self.queries.get_function_by_name(function_name).first()
        if not func_def:
            print('This function does not exist!')
            return False

        components = self.queries.list_lines_codes(
            func_def.first_char_line,
            func_def.last_char_line
        ).all()

        return [
            (comp.first_char_line, comp.last_char_line, comp.type,
             comp.name, comp.first_char_column)
            for comp in components
        ]

    def selection_args(self, line_number):
        """Get function arguments at a specific line"""
        results = self.queries.get_arguments(line_number).all()
        if results and len(results) > 0:
            return str(results[0].name)
        return -1

    @property
    def return_def(self):
        """Get all function definitions"""
        results = self.queries.get_all_function_defs().all()
        if results:
            return [(comp.name, comp.type, comp.first_char_line) for comp in results]
        else:
            print("Something went wrong in the trial verification!")
            return None

    @property
    def return_calls(self):
        """Get all function calls"""
        results = self.queries.get_all_calls().all()
        if results:
            return [(comp.name, comp.type, comp.first_char_line) for comp in results]
        else:
            print("Something went wrong in the trial verification!")
            return None

    def activation_line(self, config):
        """Get execution activations for code components"""
        results = self.queries.get_activations().all()
        if results:
            return results
        else:
            print("Something went wrong in the trial verification!")
            return None

    def runtime_line(self, config):
        """Get execution checkpoints for code components"""
        results = self.queries.get_activations().all()
        if results:
            return results
        else:
            print("Something went wrong in the trial verification!")
            return None

    def variables_content(self, config):
        """Get variable contents from evaluations"""
        results = self.queries.get_variable_contents().all()
        if results:
            return results
        else:
            print("Something went wrong in the trial verification!")
            return None

    @property
    def select_code_def_all(self):
        """Get all function definitions (line ranges only)"""
        results = self.queries.get_all_function_defs().all()
        if results:
            return [(comp.first_char_line, comp.last_char_line) for comp in results]
        else:
            print("Something went wrong in the trial verification!")
            return None
