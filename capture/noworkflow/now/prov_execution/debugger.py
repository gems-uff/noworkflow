# Copyright (c) 2015 Universidade Federal Fluminense (UFF)
# Copyright (c) 2015 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.

from __future__ import (absolute_import, print_function,
                        division, unicode_literals)

import sys
import subprocess
import threading
import webbrowser
import os
import atexit

from ..models.trial import Trial
from ..utils import redirect_output

children_pid = []

def kill_children():
    global children_pid
    for child in children_pid:
        child.kill()
    children_pid = []

atexit.register(kill_children)


def create_debugger(pdb=None):
    if pdb is None:
        from pdb import Pdb
        pdb = Pdb

    class NowDebugger(pdb):

        def __init__(self, provider, *args, **kwargs):
            self.provider = provider
            pdb.__init__(self, *args, **kwargs)

        def trace_dispatch(self, frame, event, arg):
            pdb.trace_dispatch(self, frame, event, arg)
            self.provider.tracer(frame, event, arg)
            return self.trace_dispatch

    return NowDebugger


def debugger_builtins(provider, ns, metascript):
    vis = vis_open, browser_open = [False, False]

    def set_trace(frame=None, pdb=None):
        debugger = create_debugger(pdb)(provider)
        debugger.set_trace(sys._getframe().f_back)

    def history():
        return provider.history

    def now_save():
        provider.store(partial=True)

    def now_trial(trial_id=None, save=True):
        if save:
            now_save()
        if trial_id is None:
            trial_id = metascript['trial_id']
        return Trial(trial_id)

    def now_vis(browser='maybe', port=5000, save=True, vis=vis):
        global children_pid
        vis_open, browser_open = vis
        if save:
            now_save()
        url = 'http://127.0.0.1:{0}'.format(port)
        if vis_open:
            kill_children()
            vis[0] = vis_open = False
        if not vis_open:
            params = ['now', 'vis', '-p', str(port)]
            print('now vis: {}'.format(url))
            with redirect_output():
                vis[0] = True
                FNULL = open(os.devnull, 'w')
                p = subprocess.Popen(params, stdout=FNULL, stderr=FNULL)
                children_pid.append(p)

        if browser and (browser_open ^ (browser == 'maybe')):
            def webopen(url):
                """ Workaround to redirect browser output """
                savout = os.dup(1)
                os.close(1)
                os.open(os.devnull, os.O_RDWR)
                try:
                    webbrowser.open(url)
                finally:
                    os.dup2(savout, 1)

            vis[1] = bool(browser)
            with redirect_output():
                threading.Timer(1.25, webopen, args=[url]).start()


    ns['set_trace'] = set_trace
    ns['history'] = history
    ns['now_save'] = now_save
    ns['now_trial'] = now_trial
    ns['now_vis'] = now_vis
