# Copyright (c) 2016 Universidade Federal Fluminense (UFF)
# Copyright (c) 2016 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""Debugger-related functions"""
from __future__ import (absolute_import, print_function,
                        division, unicode_literals)

import atexit
import os
import subprocess
import sys
import threading
import webbrowser

from argparse import Namespace

from ...cmd.cmd_show import Show
from ...persistence.models.trial import Trial
from ...utils.io import redirect_output


FNULL = open(os.devnull, "w")
atexit.register(FNULL.close)

CHILDREN_PID = []


def kill_children():
    """Kill debugger processes"""
    global CHILDREN_PID                                                          # pylint: disable=global-statement
    for child in CHILDREN_PID:
        child.kill()
    CHILDREN_PID = []

atexit.register(kill_children)


def create_debugger(pdb=None):
    """Create debugger"""
    if pdb is None:
        with redirect_output():
            try:
                from ipdb.__main__ import Pdb, def_colors
                pdb = Pdb(def_colors)
            except ImportError:
                from pdb import Pdb
        pdb = Pdb

    class NowDebugger(pdb):
        """Debugger that invokes both pdb tracer and noWorkflow"""

        def __init__(self, provider, *args, **kwargs):
            super(NowDebugger, self).__init__(*args, **kwargs)
            self.provider = provider

        def trace_dispatch(self, frame, event, arg):
            pdb.trace_dispatch(self, frame, event, arg)
            self.provider.tracer(frame, event, arg)
            return self.trace_dispatch

    return NowDebugger


def debugger_builtins(provider, namespace, metascript):
    """Define debugging functions"""
    vis = vis_open, browser_open = [False, False]                                # pylint: disable=unused-variable

    def set_trace(frame=None, pdb=None):                                         # pylint: disable=unused-argument
        """Invoke pdb"""
        debugger = create_debugger(pdb)(provider)
        debugger.set_trace(sys._getframe().f_back)                               # pylint: disable=protected-access

    def now_save():
        """Save partial provenance"""
        provider.store(partial=True)

    def now_trial(trial_id=None, save=True):
        """Return current trial"""
        if save:
            now_save()
        if trial_id is None:
            trial_id = metascript.trial_id
        return Trial(trial_ref=trial_id)

    def now_vis(browser="maybe", port=5000, save=True, vis=vis):                 # pylint: disable=dangerous-default-value
        """Invoke now vis"""
        vis_open, browser_open = vis
        if save:
            now_save()
        url = "http://127.0.0.1:{0}".format(port)
        if vis_open:
            kill_children()
            vis[0] = vis_open = False
        if not vis_open:
            params = ["now", "vis", "-p", str(port)]
            print("now vis: {}".format(url))
            with redirect_output():
                vis[0] = True
                proc = subprocess.Popen(params, stdout=FNULL, stderr=FNULL)
                CHILDREN_PID.append(proc)

        if browser and (browser_open ^ (browser == "maybe")):
            def webopen(url):
                """Workaround to redirect browser output"""
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

    def now_notebook(start=True):
        """Start Jupyter Notebook"""
        try:
            import IPython
            Show().execute_export(Namespace(ipynb=True, dir=None))
            if start:
                params = ["ipython", "notebook", "Current Trial.ipynb"]
                proc = subprocess.Popen(params, stdout=FNULL, stderr=FNULL)
                CHILDREN_PID.append(proc)
        except ImportError:
            return "IPython not found"

    namespace["set_trace"] = set_trace
    namespace["now_save"] = now_save
    namespace["now_trial"] = now_trial
    namespace["now_vis"] = now_vis
    namespace["now_notebook"] = now_notebook

    try:
        with redirect_output():
            from IPython import embed
            namespace["now_ipython"] = embed
    except ImportError:
        namespace["now_ipython"] = lambda: "IPython not found"
