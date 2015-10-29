# Copyright (c) 2015 Universidade Federal Fluminense (UFF)
# Copyright (c) 2015 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.

from __future__ import (absolute_import, print_function,
                        division, unicode_literals)



from collections import defaultdict, OrderedDict
from .model import Model
from ..graphs.history_graph import HistoryGraph
from ..utils import calculate_duration, FORMAT
from ..persistence import row_to_dict
from ..persistence import persistence as pers


class History(Model):
    """ This model represents the workflow evolution history

    It is possible to filter the evolution history by selecting the script:
        history.script = "script1.py"

    The list of scripts can be accessed by:
        history.scripts()

    It is also possible to filter the evolution history by selecting the
    trial status:
        history.execution = "finished"

    The list of status are:
        finished: show only finished trials
        unfinished: show only unfinished trials
        backup: show only backup trials

    The default option for both filters is "*", which means that all trials
    appear in the history
        history.script = "*"
        history.execution = "*"

    You can change the graph width and height by the variables:
        history.graph.width = 600
        history.graph.height = 200
    """

    DEFAULT = {
        'graph.width': 700,
        'graph.height': 300,
        'script': '*',
        'execution': '*',
        'data': {},
    }

    REPLACE = {
        'graph_width': 'graph.width',
        'graph_height': 'graph.height',
    }

    def __init__(self, **kwargs):
        super(History, self).__init__(**kwargs)
        self.graph = HistoryGraph()
        self.initialize_default(kwargs)
        if 'data' not in kwargs:
            self.data = {}

        self.execution_options = ["*", "finished", "unfinished", "backup"]

    def scripts(self):
        """ Returns the list of scripts used for trials """
        return {s[0].rsplit('/', 1)[-1] for s in pers.distinct_scripts()}

    def graph_data(self, script="*", execution="*"):
        """ Prepares evolution history as a dict """
        if self.script != "*" and script == "*":
            script = self.script
        if self.execution != "*" and execution == "*":
            execution = self.execution

        key = (script, execution)
        if key in self.data:
            return self.data[key]

        nodes, edges = [], []
        result = {'nodes': nodes, 'edges': edges}
        id_map, children = {}, defaultdict(list)
        scripts, order = defaultdict(list), OrderedDict()

        # Filter nodes and adds to dicts
        tid = 0
        for trial in map(row_to_dict, pers.load('trial', order="start")):
            different_script = (trial['script'] != script)
            finished = trial['finish']
            unfinished = not finished and trial['run']
            backup = not finished and not trial['run']

            if script != '*' and different_script:
                continue
            if execution == 'finished' and not finished:
                continue
            if execution == 'unfinished' and not unfinished:
                continue
            if execution == 'backup' and not backup:
                continue

            trial_id = trial["id"]
            trial["level"] = 0
            trial["status"] = "Finished" if trial["finish"] else "Unfinished"
            if not trial['run']:
                trial["status"] = "Backup"
            trial["tooltip"] = """
                <b>{script}</b><br>
                {status}<br>
                Start: {start}<br>
                Finish: {finish}
                """.format(**trial)
            if trial['finish']:
                duration = calculate_duration(trial)
                trial["tooltip"] += """
                <br>
                Duration: {duration}ns
                """.format(duration=duration)
                trial['duration'] = duration
            id_map[trial_id] = tid
            scripts[trial['script']].append(trial)
            nodes.append(trial)
            tid += 1

        # Create edges
        for trial in reversed(nodes):
            trial_id, parent_id = trial["id"], trial["parent_id"]
            if parent_id and parent_id in id_map:
                edges.append({
                    'source': id_map[trial_id],
                    'target': id_map[parent_id],
                    'right': 1,
                    'level': 0
                })
                children[parent_id].append(trial_id)
            order[trial['script']] = 1

        # Set position
        level = 0
        for script in order:
            last = level
            for trial in scripts[script]:
                trial_id, parent_id = trial["id"], trial["parent_id"]
                if parent_id and parent_id in id_map:
                    parent = nodes[id_map[parent_id]]
                    if children[parent_id].index(trial_id) > 0:
                        trial["level"] = last
                        last += 1
                    else:
                        trial["level"] = parent["level"]
                    level = max(level, trial["level"] + 1)
                else:
                    trial["level"] = level
                    level += 1
                    last += 1

        self.data[key] = result
        return result

    def _repr_html_(self):
        """ Display d3 graph on ipython notebook """
        return self.graph._repr_html_(history=self)