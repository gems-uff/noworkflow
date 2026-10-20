# Copyright (c) 2026 Universidade Federal Fluminense (UFF)
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""Process state that collecting provenance leaves behind

``Execution.collect_provenance`` changes state of the whole process: it
inserts noWorkflow's import finder in ``sys.meta_path`` and removes it only
when the script succeeds, and ``Execution.configure`` replaces the four
``open`` functions and adds names to the builtins, which nothing restores.
These tests look at the process right after the collection, before
``CollectionTestCase.tearDown`` undoes it (that tearDown is what keeps the
rest of the suite clean). Each characterization of a defect has a
``_desired`` twin that states the behavior the issue asks for, marked by
``known_defects``.
"""
from __future__ import absolute_import, division, print_function, unicode_literals

import builtins
import sys

from ..collection_testcase import CollectionTestCase
from ..helpers.defects import Defect, known_defects
from ..helpers.leaks import INJECTED_BUILTINS, OPENS, is_finder

# Where the collector's ``open`` wrapper is defined.
WRAPPER = ("noworkflow.now.collection.prov_execution.collector",
           "Collector.new_open.<locals>.open")

RAISES = ("# script.py\n"
          "1 / 0\n")
EXITS = ("# script.py\n"
         "import sys\n"
         "sys.exit(1)\n")
SUCCEEDS = ("# script.py\n"
            "x = 1\n")

FINDER_ON_ERROR = Defect(
    "#226: Execution.collect_provenance (execution.py) inserts the import "
    "finder (py3module.finder) in sys.meta_path before the exec of the "
    "script and removes it right after, with no finally, so an exception "
    "or a SystemExit leaves it there",
    signature="finder.<locals>.Finder'>")
OPENS_LEFT = Defect(
    "#250: Execution.configure (execution.py) replaces the four opens with "
    "Collector.new_open wrappers, and nothing puts the originals back when "
    "the script finishes",
    signature="['builtins.open', 'io.open', 'codecs.open', 'os.open'] "
              "!= []")
OUTSIDE_OPEN = Defect(
    "#250: the open wrappers stay after the script finishes, and the root "
    "activation is still active, so Collector.new_open records an open by "
    "code outside the script as a file access of the finished trial",
    signature="test_collector_cleanup.py' unexpectedly found in")


class TestCollectorCleanup(CollectionTestCase):
    """What the process looks like after a collection"""

    def finders(self):
        """noWorkflow's finders in sys.meta_path"""
        return [entry for entry in sys.meta_path if is_finder(entry)]

    def outside_open(self):
        """Open a file from outside the script; return the names recorded"""
        with open(__file__, "rb") as fil:
            fil.read()
        return [access.name for access
                in self.metascript.file_accesses_store.store.values()]

    def test_collecting_a_script_that_succeeds_removes_the_finder(self):
        """Control: on success the finder leaves sys.meta_path"""
        msg = self.collect(SUCCEEDS)
        self.assertEqual(msg, "the execution of trial -1 finished successfully")
        self.assertNotIn(self.metascript.definition.finder, sys.meta_path)
        self.assertEqual(self.finders(), [])

    def test_collecting_a_script_that_raises_leaves_the_finder(self):
        """The finder stays in sys.meta_path after an uncaught exception

        It is inserted and removed around ``exec`` with no ``finally``;
        #226 removes it in a try/finally. The leak detector recognizes
        this class as noWorkflow's finder.
        """
        msg = self.collect(RAISES)
        self.assertIn("the execution finished with an uncaught exception",
                      msg)
        finder = self.metascript.definition.finder
        self.assertIn(finder, sys.meta_path)
        self.assertEqual(self.finders(), [finder])

    @known_defects(FINDER_ON_ERROR)
    def test_collecting_a_script_that_raises_leaves_the_finder_desired(self):
        """Desired (#226): the finder leaves sys.meta_path on an exception"""
        self.collect(RAISES)
        self.assertEqual(self.finders(), [])

    def test_collecting_a_script_that_exits_leaves_the_finder(self):
        """The finder stays in sys.meta_path after ``sys.exit(1)``

        ``SystemExit`` is caught by its own ``except``, which never removes
        the finder; #226 removes it in a try/finally.
        """
        msg = self.collect(EXITS)
        self.assertEqual(
            msg, "the execution exited via sys.exit(). Exit status: 1")
        self.assertEqual(self.finders(), [self.metascript.definition.finder])

    @known_defects(FINDER_ON_ERROR)
    def test_collecting_a_script_that_exits_leaves_the_finder_desired(self):
        """Desired (#226): the finder leaves sys.meta_path on sys.exit()"""
        self.collect(EXITS)
        self.assertEqual(self.finders(), [])

    def test_after_collection_the_opens_are_still_the_wrappers(self):
        """The four opens are still the collector's wrappers

        Nothing puts the originals back when the script finishes
        (#250).
        """
        self.collect(SUCCEEDS)
        self.assertEqual(
            {name: (module.open.__module__, module.open.__qualname__)
             for module, name, _ in OPENS},
            {name: WRAPPER for _, name, _ in OPENS})

    @known_defects(OPENS_LEFT)
    def test_after_collection_the_opens_are_still_the_wrappers_desired(self):
        """Desired: once the script finishes, the opens are Python's again

        The original of ``builtins.open`` is ``safeopen.std_open``
        (#250).
        """
        self.collect(SUCCEEDS)
        self.assertEqual(
            [name for module, name, original in OPENS
             if module.open is not original],
            [])

    def test_after_collection_an_outside_open_is_recorded(self):
        """An ``open`` by code outside the script becomes a file access

        The leaked wrapper is not inert: the root activation is still
        active, so the finished trial keeps recording what the process
        opens (#250).
        """
        self.collect(SUCCEEDS)
        self.assertIn(__file__, self.outside_open())

    @known_defects(OUTSIDE_OPEN)
    def test_after_collection_an_outside_open_is_recorded_desired(self):
        """Desired: a finished trial records nothing else

        (#250)
        """
        self.collect(SUCCEEDS)
        self.assertNotIn(__file__, self.outside_open())

    def test_collection_adds_exactly_the_builtins_the_detector_removes(self):
        """Premise of the leak detector: it knows every injected builtin

        ``leaks.INJECTED_BUILTINS`` is what ``undo_collection`` removes and
        what the detector reports; a name the collector adds and the list
        misses would leak into every later test unnoticed.
        """
        before = set(vars(builtins))
        self.collect(SUCCEEDS)
        self.assertEqual(set(vars(builtins)) - before,
                         set(INJECTED_BUILTINS))
