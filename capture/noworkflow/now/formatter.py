# Copyright (c) 2015 Universidade Federal Fluminense (UFF)
# Copyright (c) 2015 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.


class PrettyLines(object):

    def __init__(self, lines):
        self.lines = lines

    def _repr_pretty_(self, p, cycle):
        p.text('\n'.join(self.lines))

    def __str__(self):
        return '\n'.join(self.lines)


class Table(list):

    def __init__(self, *args, **kwargs):
        super(Table, self).__init__(*args, **kwargs)
        self.show_header = True

    def _repr_html_(self):
        result = '<table>'
        it = iter(self)
        header = next(it)
        if self.show_header:
            result += '<tr>'
            result += ''.join('<th>{}</th>'.format(x) for x in header)
            result += '</tr>'
        for row in it:
            result += '<tr>'
            result += ''.join('<td>{}</td>'.format(x) for x in row)
            result += '</tr>'
        result += '</table>'
        return result