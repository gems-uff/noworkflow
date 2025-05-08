# Copyright (c) 2021 Universidade Federal Fluminense (UFF)
# Copyright (c) 2021 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
import nbformat as nbf

from copy import copy
from datetime import datetime
from ..dependency_querier import DependencyQuerier
from .merge import merge_json


def find_cell(code_component, found=None):
    """Find cells from code_components"""
    found = found or {}
    if code_component in found:
        pass
    elif code_component.type == 'cell':
        found[code_component] = code_component
    elif not code_component.container_id:
        found[code_component] = None
    else:
        found[code_component] = find_cell(code_component.container.this_component, found=found)
    return found[code_component]


def get_cells(evaluations, options=None):
    """Return cells that contribute to the creation of the evaluations"""
    result = copy(evaluations)
    querier = DependencyQuerier(options)
    visited = set()
    code_component_cell = {}
    cells = set()
    while result:
        nodes_to_visit, visited, found = querier.navigate_dependencies(result, visited=visited)
        result = []
        component_to_visit = []
        new_cells = set()
        # Extract cells from visited evaluations
        for context in visited:
            evaluation = context.evaluation

            # Evaluation cells
            component = evaluation.code_component
            cell = find_cell(component, code_component_cell)
            if cell and cell not in cells:
                new_cells.add(cell)
                cells.add(cell)
        
        # Expand dependencies to all evaluations of new cells
        for cell in new_cells:
            result.extend(cell.this_block.recursive_evaluations())

    return sorted(cells, key=lambda c: c.id)

def header(name):
    """Create markdown cell with header"""
    return nbf.v4.new_markdown_cell((
        '# History of {}\n'
        'Created at {}'
    ).format(name, datetime.now()))

def create_clean(cells, filename, name="current", create_header=True, add_empty=False, write=True):
    """Create notebook from cell code components"""
    nb = nbf.v4.new_notebook()
    nbcells = []

    if create_header:
        nbcells.append(header(name))
    
    for cell in cells:
        outputs = []
        evaluations = list(cell.evaluations)
        lineno = int(cell.name.split('-')[2])
        if evaluations and evaluations[0].repr != 'None':
            outputs.append(nbf.v4.new_output(
                output_type='execute_result',
                data={'text/plain': evaluations[0].repr},
                execution_count=lineno
            ))
        nbcells.append(nbf.v4.new_code_cell(
            str(cell.this_block.content).strip(),
            execution_count=lineno,
            outputs=outputs
        ))

    if add_empty:
        nbcells.append(nbf.v4.new_code_cell())

    nb['cells'] = nbcells
    if write:
        with open(filename, 'w') as f:
            nbf.write(nb, f)
    return nb


def create_merged_history(
    history, filename, originalfile, name,
    create_header=True, add_empty=False,
    original_first=True, merge_code=False, 
):
    """Create notebook with merged history"""
    cells = []
    after_cells = []
    if create_header:
        cells.append(header(name))
    if add_empty:
        after_cells.append(nbf.v4.new_code_cell())

    with open(originalfile) as ofile:
        original = nbf.read(ofile, 4)

    with open(filename, 'w') as f:
        nbf.write(merge_json(original, history, cells, after_cells, original_first, merge_code), f)


def create_merged_from_cells(
    cells, filename, originalfile, name,
    create_header=True, add_empty=False,
    original_first=True, merge_code=False
):
    """Create notebook with merged history from cell code components"""
    history = create_clean(
        cells, filename, name, create_header=False, add_empty=False, write=False
    )
    return create_merged_history(
        history, filename, originalfile, name,
        create_header, add_empty,
        original_first, merge_code
    )
