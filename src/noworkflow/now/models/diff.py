# Copyright (c) 2016 Universidade Federal Fluminense (UFF)
# Copyright (c) 2016 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""Diff Object"""

from __future__ import absolute_import, division, print_function, unicode_literals

import difflib
from collections import OrderedDict, defaultdict

from future.utils import viewitems, viewkeys

from ..persistence.models.base import Model, proxy_gen
from ..persistence.models.trial import Trial
from .graphs.diff_graph import DiffGraph


class Diff(Model):
    """This model represents a diff between two trials
    Initialize it by passing both trials ids:
        diff = Diff(1, 2)

    There are four visualization modes for the graph:
        tree: activation tree without any filters
            diff.graph.mode = 0
        no match: tree transformed into a graph by the addition of sequence and
                  return edges and removal of intermediate call edges
            diff.graph.mode = 1
        exact match: calls are only combined when all the sub-call match
            diff.graph.mode = 2
        namesapce: calls are combined without considering the sub-calls
            diff.graph.mode = 3


    You can change the graph width and height by the variables:
        diff.graph.width = 600
        diff.graph.height = 400
    """

    __modelname__ = "Diff"

    DEFAULT = {
        "graph.width": 500,
        "graph.height": 500,
        "graph.mode": 3,
        "graph.time_limit": None,
    }

    REPLACE = {
        "graph_width": "graph.width",
        "graph_height": "graph.height",
        "graph_mode": "graph.mode",
        "graph_time_limit": "graph.time_limit",
    }

    def __init__(self, trial_ref1, trial_ref2, **kwargs):
        super(Diff, self).__init__(trial_ref1, trial_ref2, **kwargs)
        self.trial1 = Trial(trial_ref1)
        self.trial2 = Trial(trial_ref2)

        self.graph = DiffGraph(self)
        self.initialize_default(kwargs)

    @property
    def trial(self):
        """Return a tuple with information from both trials"""
        extra = ("start", "finish", "duration_text", "code_hash")
        ignore = ("id",)
        return diff_dict(
            self.trial1.to_dict(ignore=ignore, extra=extra),  # pylint: disable=no-member
            self.trial2.to_dict(ignore=ignore, extra=extra),
        )  # pylint: disable=no-member

    @property
    def modules(self):
        """Diff modules from trials"""
        return diff_set(
            set(proxy_gen(self.trial1.modules)), set(proxy_gen(self.trial2.modules))
        )

    @property
    def environment(self):
        """Diff environment variables"""
        return diff_set(
            set(self.trial1.environment_attrs), set(self.trial2.environment_attrs)
        )

    @property
    def file_accesses(self):
        """Diff file accesses"""
        return diff_set(
            set(self.trial1.file_accesses),
            set(self.trial2.file_accesses),
            create_replaced=True,
        )

    def _ipython_display_(self):
        """Display history graph"""
        if hasattr(self, "graph"):
            # pylint: disable=protected-access
            return self.graph._ipython_display_()
        from IPython.display import display

        display({"text/plain": "Diff {}:{}".format(self.trial1.id, self.trial2.id)})


def diff_dict(before, after):
    """Compare dicts.
    Return a dict with keys shared by both dicts that have different values
        key -> [before[key], after[key]]
    """
    result = OrderedDict()
    for key in viewkeys(before):
        if key != "id" and before[key] != after[key]:
            result[key] = [before[key], after[key]]
    return result


def pairing_order(element):
    """The order in which the elements of one name are paired: by
    checkpoint, for the elements that have one (file accesses), then by id
    """
    checkpoint = getattr(element, "checkpoint", None)
    return (
        0.0 if checkpoint is None else checkpoint,
        getattr(element, "id", None) or 0,
    )


def diff_set(before, after, create_replaced=True):
    """Compare sets to get additions, removals and replacements

    Return 3 sets:
    added -- objects present in second set, but not present in first set
    removed -- objects present in first set, but not present in second set
    replaced -- pairs (removed, added) of objects that have the same name in
                both sets, but are different

    The pairs are one to one: each removed object is paired with at most
    one added object of its name, first with one of the same mode (file
    accesses), then with any that is left, in checkpoint order in both
    passes (#360). An object left without a partner stays added or
    removed. Neither pass depends on the iteration order of the sets.
    """
    removed = before - after
    added = after - before
    replaced = set()
    if not create_replaced:
        return (added, removed, replaced)

    removed_by_name = defaultdict(list)
    for element in sorted(removed, key=pairing_order):
        removed_by_name[element.name].append(element)
    added_by_name = defaultdict(list)
    for element in sorted(added, key=pairing_order):
        added_by_name[element.name].append(element)

    for name, candidates in viewitems(added_by_name):
        olds = removed_by_name.get(name)
        if not olds:
            continue
        for same_mode in (True, False):
            for element_removed in list(olds):
                for element_added in candidates:
                    if same_mode and getattr(element_removed, "mode", None) != (
                        getattr(element_added, "mode", None)
                    ):
                        continue
                    replaced.add((element_removed, element_added))
                    olds.remove(element_removed)
                    candidates.remove(element_added)
                    break
    for element_removed, element_added in replaced:
        removed.discard(element_removed)
        added.discard(element_added)

    return (added, removed, replaced)


def diff_order(element):
    """The order in which ``now diff`` prints the elements of a diff: by
    name, then in the order they are paired (the accesses to one file in
    the order of the trial)"""
    return (element.name,) + pairing_order(element)


def in_diff_order(added, removed, replaced):
    """``(added, removed, replaced)`` of ``diff_set`` as lists in
    ``diff_order``, a pair by its removed element, then its added one

    The sets iterate in the order of their hashes, which hold strings,
    randomized per process unless PYTHONHASHSEED fixes them, and None,
    whose hash comes from its address before Python 3.12: printed as they
    iterate, two runs of the same ``now diff`` gave the blocks in two
    orders (#248).
    """
    return (
        sorted(added, key=diff_order),
        sorted(removed, key=diff_order),
        sorted(replaced, key=lambda pair: (diff_order(pair[0]), diff_order(pair[1]))),
    )


# A version whose first bytes hold a NUL is shown as binary, as git does
BINARY_PROBE = 8192
# The longest unified diff `now diff --content` prints for one version
DIFF_MAX_LINES = 200


def is_binary(data):
    """Whether ``data`` (bytes) is shown as binary: a NUL byte in its first
    ``BINARY_PROBE`` bytes, or no UTF-8 text"""
    if b"\0" in data[:BINARY_PROBE]:
        return True
    try:
        data.decode("utf-8")
    except UnicodeDecodeError:
        return True
    return False


def unified_text_diff(name, label1, data1, label2, data2, max_lines=DIFF_MAX_LINES):
    """The lines of the unified diff between two versions of the file
    ``name``, or None when either one is binary

    ``data1`` and ``data2`` are bytes, or None for no file, which compares
    as an empty one. The headers read ``name (label)``. Above ``max_lines``
    the diff is cut, and a last line says how many lines were left out.
    """
    texts = []
    for data in (data1, data2):
        data = data or b""
        if is_binary(data):
            return None
        texts.append(data.decode("utf-8").splitlines())
    lines = list(
        difflib.unified_diff(
            texts[0],
            texts[1],
            fromfile="{} ({})".format(name, label1),
            tofile="{} ({})".format(name, label2),
            lineterm="",
        )
    )
    if len(lines) > max_lines:
        left_out = len(lines) - max_lines
        lines = lines[:max_lines]
        lines.append(
            "[{} more lines: `now restore <trial> -f {} -t <path>` writes a "
            "whole version]".format(left_out, name)
        )
    return lines
