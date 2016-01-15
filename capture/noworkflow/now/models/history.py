# Copyright (c) 2016 Universidade Federal Fluminense (UFF)
# Copyright (c) 2016 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""History Model"""
from __future__ import (absolute_import, print_function,
                        division, unicode_literals)

import json

from collections import defaultdict, OrderedDict
from ..graphs.history_graph import HistoryGraph
from ..persistence import row_to_dict
from ..persistence import persistence
from .model import Model
from .trial import Trial


class History(Model):
    """This model represents the workflow evolution history

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
        """Return a list of scripts used for trials"""
        return {s[0].rsplit('/', 1)[-1] for s in persistence.distinct_scripts()}

    def process_history(self, script="*", execution="*"):
        """Prepare evolution history as a dict"""
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
        for trial in persistence.session.query(Trial).order_by(Trial.start):
            different_script = (trial.script != script)
            finished = trial.finish
            unfinished = not finished and trial.run
            backup = not finished and not trial.run

            if script != '*' and different_script:
                continue
            if execution == 'finished' and not finished:
                continue
            if execution == 'unfinished' and not unfinished:
                continue
            if execution == 'backup' and not backup:
                continue

            trial_id = trial.id
            trial.level = 0
            trial.tooltip = """
                <b>{0.script}</b><br>
                {0.status}<br>
                Start: {0.start}<br>
                Finish: {0.finish}
                """.format(trial)
            if trial.finish:
                trial.tooltip += """
                <br>
                Duration: {duration}ns
                """.format(duration=trial.duration)
            id_map[trial_id] = tid
            scripts[trial.script].append(trial)
            nodes.append(trial)
            tid += 1

        # Create edges
        for trial in reversed(nodes):
            trial_id, parent_id = trial.id, trial.parent_id
            if parent_id and parent_id in id_map:
                edges.append({
                    'source': id_map[trial_id],
                    'target': id_map[parent_id],
                    'right': 1,
                    'level': 0
                })
                children[parent_id].append(trial_id)
            order[trial.script] = 1

        # Set position
        level = 0
        for script in order:
            last = level
            for trial in scripts[script]:
                trial_id, parent_id = trial.id, trial.parent_id
                if parent_id and parent_id in id_map:
                    parent = nodes[id_map[parent_id]]
                    if children[parent_id].index(trial_id) > 0:
                        trial.level = last
                        last += 1
                    else:
                        trial.level = parent.level
                    level = max(level, trial.level + 1)
                else:
                    trial.level = level
                    level += 1
                    last += 1

        self.data[key] = result

        return result

    def graph_data(self, script="*", execution="*"):
        result = self.process_history(script=script, execution=execution)

        # To JSON
        final = []
        for trial in result['nodes']:
            dic = trial.to_dict(ignore=tuple(), extra=("level", "status", "tooltip"))
            dic['start'] = str(dic['start'])
            dic['finish'] = str(dic['finish'])
            final.append(dic)
        return {'edges': result['edges'], 'nodes': final}

    def _repr_html_(self):
        """Display d3 graph on ipython notebook"""
        return self.graph._repr_html_(history=self)

    def show(self, script="*", execution="*"):
        width = max(len(s) for s in self.scripts())
        def text(active, trial, current, moving=False, width=width):
            """Return text for line history"""
            text = []
            for i, value in enumerate(active):
                if i == current:
                    text.append('/ ' if moving else
                                ' b' if not trial.run else
                                ' *' if trial.finished else
                                ' f')
                elif value:
                    text.append(' |')
                else:
                    text.append('  ')
            if moving:
                return ''.join(text)
            return "{line}  {id: <4} {script: <{width}} {tags}".format(
                line=''.join(text), id=trial.id, script=trial.script,
                tags=', '.join(tag.name for tag in trial.tags), width=width)

        history = self.process_history(script=script, execution=execution)
        trial_dict = {trial.id: trial for trial in history['nodes']}
        print(trial_dict)
        print(history['edges'])

        print(history['nodes'])
        if not trial_dict:
            return ""
        to_level = {
            edge['source'] + 1: trial_dict[edge['target']].level
            for edge in history['edges']
        }
        trials = list(reversed(history['nodes']))

        max_level = max(t.level for t in trials)
        active_levels = [0] * (max_level + 1)
        last = trials[0].level
        lines = []

        for trial in trials:
            active_levels[trial.level] = 1
            lines.append(text(active_levels, trial, trial.level))

            if not trial.id in to_level:
                active_levels[trial.level] = 0
            elif to_level[trial.id] != trial.level:
                active_levels[trial.level] = 0
                for i in range(trial.level, to_level[trial.id], -1):
                    lines.append(text(active_levels, trial, i, moving=True))

            last = trial.level

        return '\n'.join(lines)

    def __repr__(self):
        return self.show(script=self.script, execution=self.execution)
