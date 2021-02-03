# Copyright (c) 2021 Universidade Federal Fluminense (UFF)
# Copyright (c) 2021 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""Functions for merging notebooks"""
import nbformat as nbf
from collections import OrderedDict


def lcs(lis1, lis2, equals=lambda x, y: x == y):
    """Longest common subsequence for generic lists lis1, lis2
    Return two OrderedDicts representing the matches
    """
    lengths = [[0 for _ in range(len(lis2) + 1)] for _ in range(len(lis1) + 1)]
    # row 0 and column 0 are initialized to 0 already
    for in1, element1 in enumerate(lis1):
        for in2, element2 in enumerate(lis2):
            if equals(element1, element2):
                lengths[in1 + 1][in2 + 1] = lengths[in1][in2] + 1
            else:
                lengths[in1 + 1][in2 + 1] = \
                    max(lengths[in1 + 1][in2], lengths[in1][in2 + 1])
    # read the substring out from the matrix
    matches1, matches2 = OrderedDict(), OrderedDict()
    len1, len2 = len(lis1), len(lis2)
    while len1 != 0 and len2 != 0:
        if lengths[len1][len2] == lengths[len1 - 1][len2]:
            len1 -= 1
        elif lengths[len1][len2] == lengths[len1][len2 - 1]:
            len2 -= 1
        else:
            matches1[len1 - 1] = len2 - 1
            matches2[len2 - 1] = len1 - 1
            len1 -= 1
            len2 -= 1
    return matches1, matches2


class Hashable(dict):
    """Hashable dict"""
    def __key(self):
        return tuple(sorted(self.items()))

    def __hash__(self):
        return hash(self.__key())


def create_hashable(element):
    """Create hashable object recursively"""
    if isinstance(element, dict):
        return Hashable({
            k: create_hashable(v)
            for k, v in element.items()
        })
    if isinstance(element, (list, tuple)):
        return tuple(
            create_hashable(x) for x in element
        )
    if isinstance(element, set):
        return frozenset(
            create_hashable(x) for x in element
        )
    return element


def next_position(new_result, cell_matches, side, old_pointer=-1):
    """Go to the next match position, adding non matched cells"""
    for pointer in range(old_pointer + 1, len(cell_matches)):
        match = cell_matches[pointer]
        if isinstance(match[side], int):
            return pointer, match[side]
        elif match[side] != float('inf'):
            new_result.append(match)
    return len(cell_matches), float('inf')

def partial_merge(cell_matches, base_cells, side, restriction=None):
    """Merge cells from base_cells into cell_matches"""
    restriction = restriction or (lambda cell: True)
    new_result = []
    pointer, index = next_position(new_result, cell_matches, side)
    for i, cell in enumerate(base_cells):
        if i < index and restriction(cell):
            new_value = [None, None]
            new_value[side] = i
            new_result.append(tuple(new_value))
        if i == index:
            new_result.append(cell_matches[pointer])
            pointer, index = next_position(
                new_result, cell_matches, side, pointer)
        if i > index:
            raise Exception("Invalid index?")
    next_position(new_result, cell_matches, side, pointer)
    return new_result


def equal_code_cells(ocode_cell, hcode_cell):
    """Compares source of jupyter cells if they both are code cells"""
    if ocode_cell['cell_type'] != "code":
        return False 
    if hcode_cell['cell_type'] != "code":
        return False
    return ocode_cell["source"].strip() == hcode_cell["source"].strip()
    

def merge_json(original, history, before=None, after=None, original_first=True, merge_code=False):
    """Merge notebooks"""
    cells = before or []
    original_cells = [create_hashable(cell) for cell in original["cells"]]
    history_cells = [create_hashable(cell) for cell in history["cells"]]
    _, matches2 = lcs(original_cells, history_cells, equal_code_cells)
    cell_matches = list(reversed(matches2.items()))
    cell_matches.append((float('inf'), float('inf')))
    if original_first:
        first_merge = partial_merge(
            cell_matches, original_cells, 1,
            restriction=lambda cell: merge_code or cell["cell_type"] != "code"
        )
        first_merge.append((float('inf'), float('inf')))
        final_merge = partial_merge(
            first_merge, history_cells, 0,
        )
    else:
        first_merge = partial_merge(
            cell_matches, history_cells, 0,
        )
        first_merge.append((float('inf'), float('inf')))
        final_merge = partial_merge(
            first_merge, original_cells, 1,
            restriction=lambda cell: merge_code or cell["cell_type"] != "code"
        )
    for hindex, oindex in final_merge:
        if hindex is None:
            cells.append(original["cells"][oindex])
        else:
            # Use history cell even if there are matching cells
            cells.append(history["cells"][hindex])
    
    if after:
        cells.extend(after)

    nb = nbf.v4.new_notebook()
    nb["cells"] = cells

    return nb
