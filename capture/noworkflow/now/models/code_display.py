# Copyright (c) 2017 Universidade Federal Fluminense (UFF)
# Copyright (c) 2017 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""Code Display Object"""

import time
import weakref

from future.utils import viewvalues

from ..persistence import content


class CodeDisplay(object):
    """Code Display object for displaying blocks with codemirror"""

    def __init__(self, block):
        self.block = weakref.proxy(block)
        component = block.this_component
        self.first_line = component.first_char_line
        self.marks = []
        self.show_selection = True
        self._all_components = None
        self.code = content.get(block.code_hash).decode("utf-8")

    @property
    def all_components(self):
        """Returns dict with all components"""
        if self._all_components is None:
            self._all_components = {
                comp.id: comp
                for comp in self.block.all_components
            }
        return self._all_components

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

    def _repr_html_(self):
        uid = str(int(time.time() * 1000000))
        return """
            <style type="text/css">
              .mark-text {{ background-color: lightblue; }}
            </style>
            <textarea id="{0}">\n{1}
            </textarea>
            <script>
            var code_id = "{0}";
            var code_mirror = CodeMirror.fromTextArea(
              document.getElementById(code_id), {{
              lineNumbers: true,
              styleSelectedText: true,
              mode: "python",
              readOnly: true
            }});

            marks = {2};
            marks.forEach(function(mark) {{
              code_mirror.markText.apply(code_mirror, mark)
            }});

            show_selection = {3};
            if (show_selection) {{
              $(code_mirror.getWrapperElement()).after(
                "<input type='text' id='"+code_id+"-selection'></input>"
              );
              code_mirror.on('cursorActivity', function(cm) {{
                var tcursor = cm.getCursor(true);
                var fcursor = cm.getCursor(false);
                $("#"+code_id+"-selection").val(
                  "[" + tcursor.line + ", " + tcursor.ch + "], "+
                  "[" + fcursor.line + ", " + fcursor.ch + "]"
                );
              }});
            }}
            </script>
        """.format(
            uid,
            self.block.content,
            self.marks,
            int(self.show_selection)
        )

    def __str__(self):
        """Default str repr"""
        return self.code
