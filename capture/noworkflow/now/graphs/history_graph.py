# Copyright (c) 2015 Universidade Federal Fluminense (UFF)
# Copyright (c) 2015 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
""" History Graph Module """
from __future__ import (absolute_import, print_function,
                        division, unicode_literals)

import time

from .structures import Graph


class HistoryGraph(Graph):
    """ History Graph Class
        Present history graph on Jupyter"""
    # pylint: disable=R0201

    def __init__(self, width=500, height=500):
        self.width = width
        self.height = height

    def graph(self, history=None, script="*", execution="*"):
        """ Return history graph"""
        if not history:
            from ..models import History
            history = History()
        return history.graph_data(script=script, execution=execution)

    def _repr_html_(self, history=None):
        """ Display d3 graph on ipython notebook """
        uid = str(int(time.time()*1000000))

        result = """
            <div class="nowip-history" data-width="{width}"
                 data-height="{height}" data-uid="{uid}">
                {data}
            </div>
        """.format(
            uid=uid,
            data=self.escape_json(self.graph(history=history)),
            width=self.width, height=self.height)
        return result
