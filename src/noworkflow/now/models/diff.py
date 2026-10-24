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
# The longest edit script `now diff --content` looks for with Myers'
# algorithm, whose time grows with its square; past it the diff is
# difflib's, quick but not always minimal, and longer than DIFF_MAX_LINES
DIFF_MAX_EDITS = 2000
# Unchanged lines shown around each change, as `diff -u` does
DIFF_CONTEXT = 3


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


def common_run(a, b, x, y):
    """How many lines ``a[x:]`` and ``b[y:]`` share at their start

    Compares slices that double in length, then halves the one that
    differs, so that a long run of equal lines costs a few list
    comparisons instead of a Python step per line.
    """
    limit = min(len(a) - x, len(b) - y)
    if limit <= 0 or a[x] != b[y]:
        return 0
    low, step = 1, 1
    while low < limit:
        high = min(low + step, limit)
        if a[x + low : x + high] == b[y + low : y + high]:
            low, step = high, step * 2
            continue
        while high - low > 1:
            middle = (low + high) // 2
            if a[x + low : x + middle] == b[y + low : y + middle]:
                low = middle
            else:
                high = middle
        break
    return low


def shortest_edit_script(a, b, max_edits=DIFF_MAX_EDITS):
    """The changes of a shortest edit script from ``a`` to ``b``, or None
    when it takes more than ``max_edits`` removed and added lines

    Myers' greedy algorithm ("An O(ND) Difference Algorithm and Its
    Variations", 1986), as `diff` and `git diff` use it: its time grows
    with the length of the texts times the number of edits, and repeated
    lines do not slow it down. Each change is ``(i1, i2, j1, j2)``:
    ``a[i1:i2]`` is replaced by ``b[j1:j2]``, in order, with equal lines
    between two changes.
    """
    n, m = len(a), len(b)
    if abs(n - m) > max_edits:
        return None
    offset = max_edits + 1
    # The furthest x reached on each diagonal k = x - y, at index offset + k
    furthest = [0] * (2 * max_edits + 3)
    trace = []
    for edits in range(max_edits + 1):
        for k in range(-edits, edits + 1, 2):
            if k == -edits or (
                k != edits and furthest[offset + k - 1] < furthest[offset + k + 1]
            ):
                x = furthest[offset + k + 1]
            else:
                x = furthest[offset + k - 1] + 1
            x += common_run(a, b, x, x - k)
            furthest[offset + k] = x
            if x >= n and x - k >= m:
                trace.append(furthest[offset - edits : offset + edits + 1])
                return compact_changes(a, b, script_changes(trace, n, m))
        trace.append(furthest[offset - edits : offset + edits + 1])
    return None


def script_changes(trace, n, m):
    """The changes of the path that ``shortest_edit_script`` found, walked
    back from ``(n, m)`` through the furthest x of each diagonal after
    each number of edits (``trace``)"""
    edits = []
    x, y = n, m
    for count in range(len(trace) - 1, 0, -1):
        # Diagonals -(count - 1) to count - 1, after one edit fewer
        before = trace[count - 1]
        diagonal = x - y
        index = diagonal + count - 1
        removed = not (
            diagonal == -count
            or (diagonal != count and before[index - 1] < before[index + 1])
        )
        # From diagonal + 1, b[y] was added; from diagonal - 1, a[x] removed
        diagonal += -1 if removed else 1
        x = before[diagonal + count - 1]
        y = x - diagonal
        edits.append((x, y, removed))
    changes = []
    for x, y, removed in reversed(edits):
        if changes and changes[-1][1] == x and changes[-1][3] == y:
            i1, i2, j1, j2 = changes.pop()
        else:
            i1, i2, j1, j2 = x, x, y, y
        changes.append((i1, i2 + 1, j1, j2) if removed else (i1, i2, j1, j2 + 1))
    return changes


def compact_changes(a, b, changes):
    """``changes`` with each change that only removes or only adds lines
    slid over the equal lines that separate it from its neighbor, when
    they repeat its own, and merged with it

    A shortest edit script can remove a row here and add its replacement
    rows below, when every row between them is the same; this puts the
    two together, as `diff` does. The number of edits does not change.
    """
    merged = []
    for change in changes:
        if merged:
            joined = slide_up(a, b, merged[-1], change) or slide_down(
                a, b, merged[-1], change
            )
            if joined:
                merged[-1] = joined
                continue
        merged.append(change)
    return merged


def slide_up(a, b, previous, change):
    """``previous`` and ``change`` merged, with ``change`` slid up to the
    end of ``previous``, or None when it cannot slide"""
    i1, i2, j1, j2 = change
    gap = i1 - previous[1]
    if j1 == j2 and a[i1 - gap : i1] == a[i2 - gap : i2]:
        return (previous[0], i2 - gap, previous[2], previous[3])
    if i1 == i2 and b[j1 - gap : j1] == b[j2 - gap : j2]:
        return (previous[0], previous[1], previous[2], j2 - gap)
    return None


def slide_down(a, b, previous, change):
    """``previous`` and ``change`` merged, with ``previous`` slid down to
    the start of ``change``, or None when it cannot slide"""
    i1, i2, j1, j2 = previous
    gap = change[0] - i2
    if j1 == j2 and a[i1 : i1 + gap] == a[i2 : i2 + gap]:
        return (i1 + gap, change[1], change[2], change[3])
    if i1 == i2 and b[j1 : j1 + gap] == b[j2 : j2 + gap]:
        return (change[0], change[1], j1 + gap, change[3])
    return None


def changed_blocks(a, b, max_edits=DIFF_MAX_EDITS):
    """The changes from ``a`` to ``b``: a shortest edit script, or
    difflib's when that would take more than ``max_edits`` edits"""
    changes = shortest_edit_script(a, b, max_edits)
    if changes is not None:
        return changes
    matcher = difflib.SequenceMatcher(None, a, b)
    return [code[1:] for code in matcher.get_opcodes() if code[0] != "equal"]


def unified_range(start, stop):
    """A range of a hunk header, as `diff -u` writes it"""
    if stop - start == 1:
        return str(start + 1)
    return "{},{}".format(start + 1 if stop > start else start, stop - start)


def unified_lines(a, b, changes, fromfile, tofile, context=DIFF_CONTEXT):
    """The lines of the unified diff of ``changes`` from ``a`` to ``b``,
    in the format of ``difflib.unified_diff`` with ``lineterm=""``: two
    changes closer than ``2 * context`` equal lines share a hunk"""
    hunks = []
    for change in changes:
        if hunks and change[0] - hunks[-1][-1][1] <= 2 * context:
            hunks[-1].append(change)
        else:
            hunks.append([change])
    lines = ["--- " + fromfile, "+++ " + tofile] if hunks else []
    for hunk in hunks:
        first, last = hunk[0], hunk[-1]
        before = min(context, first[0])
        after = min(context, len(a) - last[1])
        x, y = first[0] - before, first[2] - before
        lines.append(
            "@@ -{} +{} @@".format(
                unified_range(x, last[1] + after), unified_range(y, last[3] + after)
            )
        )
        for i1, i2, j1, j2 in hunk:
            lines.extend(" " + line for line in a[x:i1])
            lines.extend("-" + line for line in a[i1:i2])
            lines.extend("+" + line for line in b[j1:j2])
            x = i2
        lines.extend(" " + line for line in a[x : last[1] + after])
    return lines


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
    lines = unified_lines(
        texts[0],
        texts[1],
        changed_blocks(texts[0], texts[1]),
        "{} ({})".format(name, label1),
        "{} ({})".format(name, label2),
    )
    if len(lines) > max_lines:
        left_out = len(lines) - max_lines
        lines = lines[:max_lines]
        lines.append(
            "[{} more lines: `now restore <trial> -f {} -t <path>` writes a "
            "whole version]".format(left_out, name)
        )
    return lines
