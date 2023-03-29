# Copyright (c) 2017 Universidade Federal Fluminense (UFF)
# Copyright (c) 2017 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""Code Display Object"""

import time

from future.utils import viewvalues

from ..persistence import content


class CodeDisplay(object):
    """Code Display object for displaying blocks with codemirror"""
    # pylint: disable=too-few-public-methods

    def __init__(self, block):
        if block is not None:
            component = block.this_component
            self.trial_id = block.trial_id
            self.first_line = component.first_char_line
            self.marks = []
            self.show_selection = False
            self.all_components = {
                comp.id: comp
                for comp in block.all_components
            }
            self.code = content.get(block.code_hash).decode("utf-8")

    def __getitem__(self, item):
        code = self.code.split('\n')
        if isinstance(item, slice):
            start_line = item.start or self.first_line
            start = item.start - self.first_line if item.start else None
            stop = item.stop - self.first_line if item.stop else None
            newslice = slice(start, stop, item.step)
            code = "\n".join(code[newslice])
        elif isinstance(item, int):
            start_line = item
            code = "\n".join(code[item])
        else:
            raise IndexError("Invalid index {}".format(item))
        result = CodeDisplay(None)
        result.trial_id = self.trial_id
        result.first_line = start_line
        result.marks = []
        result.show_selection = False
        result.all_components = self.all_components
        result.code = code
        return result

    def get_mark(self, component, properties):
        """Get a codemirror mark definition"""
        return [
            {'line': component.first_char_line - self.first_line,
             'ch': component.first_char_column},
            {'line': component.last_char_line - self.first_line,
             'ch': component.last_char_column},
            properties
        ]

    def __call__(self, marks=None, show_evaluations=True, show_selection=True):
        self.marks = marks or []
        self.show_selection = show_selection
        if show_evaluations:
            self.marks += [
                self.get_mark(
                    comp,
                    {'title': ", ".join([str(e.id) for e in comp.evaluations])}
                )
                for comp in viewvalues(self.all_components)
            ]
        return self
    
    def _ipython_display_(self):
        from IPython.display import display
        bundle = {
            'text/plain': self.code,
            'application/noworkflow.code+json': {
                'code': self.code,
                'marks': self.marks,
                'showSelection': self.show_selection,
                'firstLineNumber': self.first_line
            }
        }
        display(bundle, raw=True)

    def __str__(self):
        """Default str repr"""
        return self.code

    def _code_component_query(self, first_char, last_char, id_=None):
        """Return code component query for interval [first_char, last_char]
        Where:
          first_char = [first_char_line, first_char_column]
          last_char = [last_char_line, last_char_column]
        """
        from ...patterns import code_component, var
        line = self.first_line
        id_ = id_ or var("_id")
        return code_component(
            self.trial_id,
            id_,
            ((code_component.first_char_line == first_char[0] + line) &
             (code_component.first_char_column >= first_char[1])) |
            (code_component.first_char_line > first_char[0] + line),
            ((code_component.last_char_line == last_char[0] + line) &
             (code_component.last_char_column <= last_char[1])) |
            (code_component.last_char_line < last_char[0] + line),
        )

    def find_code_components(self, first_char, last_char):
        """Return code components for interval [first_char, last_char]
        Where:
          first_char = [first_char_line, first_char_column]
          last_char = [last_char_line, last_char_column]
        """
        for component, _ in self._code_component_query(first_char, last_char):
            yield component

    def _evaluation_query(self, first_char, last_char):
        """Return evalation query for interval [first_char, last_char]
        Where:
          first_char = [first_char_line, first_char_column]
          last_char = [last_char_line, last_char_column]
        """
        from ...patterns import evaluation, var
        code_id = var("_code_id")
        return (
            self._code_component_query(first_char, last_char, code_id) &
            evaluation(self.trial_id, code_component_id=code_id)
        )

    def find_evaluations(self, first_char, last_char):
        """Return evalations for interval [first_char, last_char]
        Where:
          first_char = [first_char_line, first_char_column]
          last_char = [last_char_line, last_char_column]
        """
        for code_eval, _ in self._evaluation_query(first_char, last_char):
            yield code_eval[1]
