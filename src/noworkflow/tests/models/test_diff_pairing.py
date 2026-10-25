# Copyright (c) 2026 Universidade Federal Fluminense (UFF)
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""The pure functions behind ``now diff``: pairs, order and content diffs

``diff_set`` (``models/diff.py``) splits the elements of two trials into
added, removed and replaced; ``in_diff_order`` gives the order ``now
diff`` prints them in; ``unified_text_diff`` is what ``--content`` prints
for two versions of a file (#204), a shortest edit script found by Myers'
algorithm (#466). The elements here stand for file
accesses (a name, a mode, a content hash, a checkpoint and an id) and for
modules (a name and a hash, no mode, no checkpoint); like the models, they
are equal when the name, the mode and the hash are, whatever the
checkpoint and the id. Each pairing case is built in several insertion
orders, since the sets ``diff_set`` receives iterate in an order that
changes with the hash seed (#360).
"""

import dataclasses
import difflib
import itertools
import random
import time

import pytest

from noworkflow.now.models.diff import (
    DIFF_MAX_EDITS,
    DIFF_MAX_LINES,
    changed_blocks,
    diff_set,
    in_diff_order,
    shortest_edit_script,
    unified_lines,
    unified_text_diff,
)


@dataclasses.dataclass(frozen=True)
class Access:
    """A file access as ``diff_set`` sees it"""

    name: str
    mode: str
    content: str
    checkpoint: float = dataclasses.field(compare=False)
    id: int = dataclasses.field(compare=False)


@dataclasses.dataclass(frozen=True)
class Module:
    """A module as ``diff_set`` sees it: no mode, no checkpoint"""

    name: str
    code_hash: str
    id: int = dataclasses.field(compare=False)


def every_order(elements):
    """Sets of ``elements`` built in each insertion order"""
    return [set(order) for order in itertools.permutations(elements)]


def pairs(replaced):
    """``replaced`` as sorted ``(id, id)`` pairs"""
    return sorted((old.id, new.id) for old, new in replaced)


def ids(elements):
    return sorted(element.id for element in elements)


def check_every_order(before, after, expected):
    """``diff_set`` gives ``expected`` (added ids, removed ids, pairs of
    ids) for every insertion order of both sets"""
    for first in every_order(before):
        for second in every_order(after):
            added, removed, replaced = diff_set(first, second)
            assert (ids(added), ids(removed), pairs(replaced)) == expected


def test_a_write_and_a_read_of_one_file_pair_by_mode():
    """The case of #360: a file written and read back in both trials, with
    another content: the write pairs with the write, the read with the
    read, nothing is added or removed"""
    before = [Access("out.txt", "w", "a", 1.0, 1), Access("out.txt", "r", "a", 2.0, 2)]
    after = [Access("out.txt", "w", "b", 1.5, 11), Access("out.txt", "r", "b", 2.5, 12)]
    check_every_order(before, after, ([], [], [(1, 11), (2, 12)]))


def test_accesses_of_one_name_and_mode_pair_in_the_order_of_the_trial():
    """Three reads of one file in each trial pair first with first, second
    with second and third with third, by checkpoint, not by id or by the
    order of the sets"""
    before = [
        Access("in.txt", "r", c, t, i)
        for c, t, i in (("a", 1, 3), ("b", 2, 1), ("c", 3, 2))
    ]
    after = [
        Access("in.txt", "r", c, t, i)
        for c, t, i in (("x", 4, 12), ("y", 5, 13), ("z", 6, 11))
    ]
    check_every_order(before, after, ([], [], [(1, 13), (2, 11), (3, 12)]))


def test_an_access_whose_mode_changed_pairs_with_the_one_left():
    """A read in the first trial and a write in the second: no access of
    the same mode, so they pair with each other, and ``now diff`` prints
    the mode change"""
    before = [Access("data.txt", "r", "a", 1.0, 1)]
    after = [Access("data.txt", "w", "b", 1.0, 2)]
    check_every_order(before, after, ([], [], [(1, 2)]))


def test_the_same_mode_wins_over_the_order_of_the_trial():
    """The second trial writes before it reads: its read still pairs with
    the first trial's read, its write with the write"""
    before = [Access("f", "r", "a", 1.0, 1), Access("f", "w", "b", 2.0, 2)]
    after = [Access("f", "w", "c", 1.0, 11), Access("f", "r", "d", 2.0, 12)]
    check_every_order(before, after, ([], [], [(1, 12), (2, 11)]))


def test_an_access_left_without_a_partner_stays_removed_or_added():
    """Two changed writes in the first trial and one in the second: one
    pair, the first write with the write, and the other write removed; the
    reverse leaves it added. Each access is used once"""
    first = [Access("log", "w", "a", 1.0, 1), Access("log", "w", "b", 2.0, 2)]
    second = [Access("log", "w", "c", 1.0, 11)]
    check_every_order(first, second, ([], [2], [(1, 11)]))
    check_every_order(second, first, ([2], [], [(11, 1)]))


def test_unchanged_and_other_names_do_not_pair():
    """An access equal in both trials is neither added, removed nor
    replaced; accesses of different names never pair"""
    same = Access("same", "r", "s", 1.0, 1)
    before = [same, Access("old", "r", "a", 2.0, 2)]
    after = [Access("same", "r", "s", 9.0, 11), Access("new", "r", "b", 2.0, 12)]
    check_every_order(before, after, ([12], [2], []))


def test_elements_without_mode_or_checkpoint_pair_by_id():
    """Two rows of one module in each trial (a program rebuilt during the
    trial, #203) pair in the order of their ids"""
    before = [Module("metrics", "a", 2), Module("metrics", "b", 1)]
    after = [Module("metrics", "c", 11), Module("metrics", "d", 12)]
    check_every_order(before, after, ([], [], [(1, 11), (2, 12)]))


def test_no_pairs_when_replaced_is_not_asked():
    before = {Access("f", "r", "a", 1.0, 1)}
    after = {Access("f", "r", "b", 1.0, 2)}
    added, removed, replaced = diff_set(before, after, create_replaced=False)
    assert (ids(added), ids(removed), replaced) == ([2], [1], set())


def test_in_diff_order_sorts_by_name_then_by_the_order_of_the_trial():
    """``now diff`` prints each section by name, and the accesses to one
    file in the order of the trial; a pair goes by its removed element"""
    accesses = [
        Access("b", "r", "1", 2.0, 4),
        Access("a", "w", "1", 3.0, 1),
        Access("b", "w", "1", 1.0, 5),
        Access("a", "r", "1", 1.0, 2),
    ]
    pairs_ = [(access, access) for access in accesses]
    for order in itertools.permutations(range(len(accesses))):
        added, removed, replaced = in_diff_order(
            {accesses[i] for i in order},
            {accesses[i] for i in order},
            {pairs_[i] for i in order},
        )
        expected = [2, 1, 5, 4]
        assert [a.id for a in added] == [a.id for a in removed] == expected
        assert [old.id for old, _ in replaced] == expected


# --- unified_text_diff -------------------------------------------------------


def test_unified_text_diff_of_two_texts():
    lines = unified_text_diff(
        "model.R", "trial 1", b"a\nx <- 1\nb\n", "trial 2", b"a\nx <- 2\nb\n"
    )
    assert lines == [
        "--- model.R (trial 1)",
        "+++ model.R (trial 2)",
        "@@ -1,3 +1,3 @@",
        " a",
        "-x <- 1",
        "+x <- 2",
        " b",
    ]


def test_unified_text_diff_reads_no_file_as_empty():
    lines = unified_text_diff("out.txt", "trial 1", None, "trial 2", b"F1=0.7\n")
    assert lines == [
        "--- out.txt (trial 1)",
        "+++ out.txt (trial 2)",
        "@@ -0,0 +1 @@",
        "+F1=0.7",
    ]


def test_unified_text_diff_of_equal_texts_is_empty():
    assert unified_text_diff("a", "1", b"same\n", "2", b"same\n") == []


@pytest.mark.parametrize(
    "data1, data2",
    [
        pytest.param(b"\x7fELF\0\0\x01", b"text\n", id="nul-first"),
        pytest.param(b"text\n", b"\xff\xfe\x00a", id="nul-second"),
        pytest.param(b"caf\xe9\n", b"cafe\n", id="not-utf-8"),
        pytest.param(b"x" * 8191 + b"\0", b"x\n", id="nul-at-the-edge"),
    ],
)
def test_unified_text_diff_of_binary_content_is_none(data1, data2):
    """A NUL in the first 8 KiB, or bytes that are not UTF-8, make a
    version binary: no diff"""
    assert unified_text_diff("metrics", "1", data1, "2", data2) is None


def test_a_nul_past_the_probe_is_text():
    """Past the first 8 KiB a NUL no longer makes the content binary"""
    lines = unified_text_diff("big", "1", b"x" * 8192 + b"\0\n", "2", b"y\n")
    assert lines is not None and lines[0] == "--- big (1)"


def test_unified_text_diff_is_cut_at_max_lines_with_a_hint():
    old = "".join("{}\n".format(i) for i in range(300)).encode()
    full = unified_text_diff(
        "data.csv", "trial 1", old, "trial 2", b"", max_lines=len(old)
    )
    assert len(full) > DIFF_MAX_LINES
    lines = unified_text_diff("data.csv", "trial 1", old, "trial 2", b"")
    assert lines[:DIFF_MAX_LINES] == full[:DIFF_MAX_LINES]
    assert lines[DIFF_MAX_LINES:] == [
        "[{} more lines: `now restore <trial> -f data.csv -t <path>` writes a "
        "whole version]".format(len(full) - DIFF_MAX_LINES)
    ]
    short = unified_text_diff("data.csv", "trial 1", old, "trial 2", b"", max_lines=5)
    assert len(short) == 6 and short[:5] == full[:5]


# A CSV of predictions where most rows repeat, and two rows that change
REPEATED = ["Class,Pred"] + ["0,0"] * 3000 + ["1,1"] + ["0,0"] * 3000
CHANGED = list(REPEATED)
CHANGED[1000] = CHANGED[4500] = "0,1"


def changed_lines(lines):
    """The removed and added lines of a unified diff, without its headers"""
    return [line for line in lines[2:] if line[:1] in "-+"]


def as_bytes(lines):
    return "".join(line + "\n" for line in lines).encode()


def uncut_diff(old, new):
    """``unified_text_diff`` of two lists of lines, whole"""
    return unified_text_diff(
        "pred.csv", "1", as_bytes(old), "2", as_bytes(new), max_lines=float("inf")
    )


def test_unified_text_diff_of_repeated_lines_is_minimal():
    """Two rows changed among six thousand repeated ones: the diff removes
    and adds those two rows, each next to its replacement, and nothing
    else (#466: difflib's autojunk anchored nothing there and removed and
    added 3006 lines)"""
    changed = changed_lines(uncut_diff(REPEATED, CHANGED))
    assert len(changed) == 4, "{} changed lines".format(len(changed))
    lines = unified_text_diff(
        "pred.csv", "1", as_bytes(REPEATED), "2", as_bytes(CHANGED)
    )
    hunk = [" 0,0"] * 3 + ["-0,0", "+0,1"] + [" 0,0"] * 3
    assert lines == [
        "--- pred.csv (1)",
        "+++ pred.csv (2)",
        "@@ -998,7 +998,7 @@",
        *hunk,
        "@@ -4498,7 +4498,7 @@",
        *hunk,
    ]


def apply_changes(a, b, changes):
    """``a`` with each change ``(i1, i2, j1, j2)`` applied: ``a[i1:i2]``
    replaced by ``b[j1:j2]``"""
    result, position = [], 0
    for i1, i2, j1, j2 in changes:
        assert position <= i1 <= i2 and j1 <= j2, changes
        result += a[position:i1] + b[j1:j2]
        position = i2
    return result + a[position:]


def longest_common_subsequence(a, b):
    """Its length, by dynamic programming"""
    row = [0] * (len(b) + 1)
    for line in a:
        previous, row = row, [0]
        for j, other in enumerate(b):
            row.append(
                previous[j] + 1 if line == other else max(previous[j + 1], row[j])
            )
    return row[-1]


def random_texts(seed, count):
    """``count`` pairs of short texts over small alphabets, so that lines
    repeat and many edit scripts are equally short"""
    rng = random.Random(seed)
    for _ in range(count):
        alphabet = rng.choice(["ab", "abc", "aaab", "abcdef"])
        yield (
            [rng.choice(alphabet) for _ in range(rng.randint(0, 30))],
            [rng.choice(alphabet) for _ in range(rng.randint(0, 30))],
        )


def test_the_changes_are_a_shortest_edit_script():
    """On random texts, the changes turn the first text into the second,
    with equal lines between two of them, and remove and add as few lines
    as the longest common subsequence allows"""
    for a, b in random_texts(466, 2000):
        changes = shortest_edit_script(a, b, len(a) + len(b))
        assert apply_changes(a, b, changes) == b, (a, b, changes)
        assert all(left[1] < right[0] for left, right in zip(changes, changes[1:]))
        edits = sum(i2 - i1 + j2 - j1 for i1, i2, j1, j2 in changes)
        assert edits == len(a) + len(b) - 2 * longest_common_subsequence(a, b), (
            a,
            b,
            changes,
        )


@pytest.mark.parametrize("context", [0, 1, 3])
def test_unified_lines_print_what_difflib_prints(context):
    """Given difflib's own changes, the hunks, their headers and their
    context are those of ``difflib.unified_diff``"""
    for a, b in random_texts(204, 500):
        matcher = difflib.SequenceMatcher(None, a, b)
        changes = [code[1:] for code in matcher.get_opcodes() if code[0] != "equal"]
        assert unified_lines(a, b, changes, "x (1)", "x (2)", context) == list(
            difflib.unified_diff(a, b, "x (1)", "x (2)", lineterm="", n=context)
        ), (a, b)


def test_a_script_longer_than_max_edits_is_not_searched():
    """Past ``max_edits`` the search gives up, and the changes are
    difflib's: valid, but not always the fewest"""
    a, b = ["x"] * 10 + ["y"] * 5, ["y"] * 5 + ["x"] * 10
    assert shortest_edit_script(a, b, max_edits=9) is None
    assert shortest_edit_script(a, b, max_edits=10) == [(0, 0, 0, 5), (10, 15, 15, 15)]
    matcher = difflib.SequenceMatcher(None, a, b)
    assert changed_blocks(a, b, max_edits=9) == [
        code[1:] for code in matcher.get_opcodes() if code[0] != "equal"
    ]
    assert apply_changes(a, b, changed_blocks(a, b, max_edits=9)) == b


@pytest.mark.parametrize(
    "flips",
    [
        pytest.param(9, id="few-changes"),
        pytest.param(DIFF_MAX_EDITS, id="past-max-edits"),
    ],
)
def test_a_large_file_of_repeated_lines_diffs_in_bounded_time(flips):
    """A 200,000-row CSV of repeated rows with ``flips`` rows changed: with
    a few, the shortest script; with more edits than ``DIFF_MAX_EDITS``,
    difflib's after the search gives up; either way in seconds"""
    rng = random.Random(flips)
    old = ["0,0"] * 200_000
    new = list(old)
    for row in rng.sample(range(len(old)), flips):
        new[row] = "0,1"
    started = time.perf_counter()
    changes = changed_blocks(old, new)
    elapsed = time.perf_counter() - started
    assert apply_changes(old, new, changes) == new
    if flips < DIFF_MAX_EDITS // 2:
        assert sum(i2 - i1 + j2 - j1 for i1, i2, j1, j2 in changes) == 2 * flips
    assert elapsed < 20, "{:.1f}s for {} rows changed".format(elapsed, flips)
