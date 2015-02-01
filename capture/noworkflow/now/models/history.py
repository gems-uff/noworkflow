# Copyright (c) 2014 Universidade Federal Fluminense (UFF)
# Copyright (c) 2014 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.

from __future__ import (absolute_import, print_function,
                        division, unicode_literals)

from collections import defaultdict, OrderedDict
from .utils import calculate_duration, FORMAT
from ..persistence import row_to_dict
from ..persistence import persistence as pers

class History(object):
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
        history.graph_width = 600
        history.graph_height = 200
    """

    def __init__(self):
        self.data = {}
        self.script = "*"
        self.execution = "*"

        self.execution_options = ["*", "finished", "unfinished", "backup"]
        self.graph_width = 700
        self.graph_height = 300

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
                trial["tooltip"] += """
                <br>
                Duration: {duration}ns
                """.format(duration=calculate_duration(trial))
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

    def _ipython_display_(self):
        """ Displays d3 graph on ipython notebook """
        from IPython.display import (
            display_png, display_html, display_latex,
            display_javascript, display_svg
        )
        import json
        import time

        uid = str(int(time.time()*1000000))
        display_html("""
            <div class="now-history now">
                <div>
                    <div class="toolbar">
                       <a class="toollink" id="restore-history-zoom-{0}" href="#" title="Restore zoom"><i class="fa fa-eye"></i></a>
                       <input id="show-history-tooltips-{0}" type="checkbox" name="show-history-tooltips" value="show">
                       <label for="show-history-tooltips-{0}" title="Show tooltips on mouse hover"><i class="fa fa-comment"></i></label>
                    </div>
                    <div id='history-{0}' class="now-history-graph ipython-graph" style="width: {1}px; height: {2}px;"></div>
                </div>
            </div>""".format(uid, self.graph_width, self.graph_height), raw=True)
        display_javascript("""
            var hg = now_history_graph('#history-{0}', {0}, {1}, {2}, {3}, "#show-history-tooltips-{0}", {{
                custom_size: function() {{
                    return [{2}, {3}];
                }},
                hint_message: "",
            }});

            $( "[name='show-history-tooltips']" ).change(function() {{
                hg.graph.set_use_tooltip(d3.select("#show-history-tooltips-{0}").property("checked"));
            }});

            $('#restore-history-zoom-{0}').on('click', function(e){{
                hg.graph.reset_zoom();
            }});
            """.format(
                uid,
                json.dumps(self.graph_data()),
                self.graph_width, self.graph_height), raw=True)
