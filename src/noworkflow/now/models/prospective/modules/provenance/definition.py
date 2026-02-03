# Copyright (c) 2016 Universidade Federal Fluminense (UFF)
# Copyright (c) 2016 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""Definition provenance analyzer - builds control flow graphs"""
from __future__ import (absolute_import, print_function,
                        division, unicode_literals)

from collections import defaultdict
from typing import List, Optional, Dict, Any

from ..build.syntax_utils import SyntaxUtils
from ..build.graph_drawer import GraphDrawer
from ..build.node_mapper import NodeMapper
from ..build.condition_nodes import ConditionNodes
from ..build.graphviz_wrapper import GraphvizWrapper


class DefinitionProvenanceAnalyzer:
    """Analyzes code structure and builds control-flow provenance graph"""

    def __init__(self, trial_id: str):
        self.trial_id = trial_id
        self.provenance = GraphvizWrapper(trial_id).initialize()
        self.collector = None

        self.def_list: List[Optional[str]] = []
        self.call: Dict[str, List[str]] = defaultdict(list)
        self.defs: Dict[str, List[str]] = defaultdict(list)
        self.visited_x: List[str] = []
        self.visited_y: List[str] = []

        self.def_method: Dict[str, List] = defaultdict(list)
        self.class_method: List = []

        self.class_def_name: List[str] = []
        self.class_def_start: List[int] = []
        self.class_def_final: List[int] = []

        self.hash_index: List[int] = []

        self.try_except: Dict[str, List[str]] = defaultdict(list)

        self.def_function: List[str] = []
        self.singleIF: List[Optional[str]] = []
        self.generic_hash: List[str] = []
        self.def_function_final: List[str] = []
        self.def_function_after: List[str] = []

        self.class_list: List[str] = []
        self.start: List[int] = []
        self.column: List[int] = []
        self.last: List[int] = []
        self.block: List[str] = []
        self.type: List[str] = []

        self.node_hash: List[str] = []
        self.node_else: List[Optional[str]] = []
        self.node_if: List[Optional[str]] = []
        self.node_for: List[Optional[str]] = []
        self.node_for_sup: List[Optional[str]] = []
        self.node_end_for: List[Optional[str]] = []
        self.arrayHashing: Dict[int, List] = defaultdict(list)

    def syntax_rules_if(self):
        """Apply IF/ELIF/ELSE control flow rules"""
        self._format_condition_node()
        self._create_condition_node()
        self._organize_sequences_if_else()
        self._update_sequences_if_else()

    def syntax_rules_for(self):
        """Apply FOR/WHILE loop control flow rules"""
        self._get_call_back()
        self._get_call_ends()
        self._get_last_loop()

    def syntax_rules_try(self):
        """Apply TRY/EXCEPT/FINALLY control flow rules"""
        self._check_try()
        self._get_call_try_exception()

    def _create_condition_node(self):
        """Tag condition elements with their parent IF node"""
        for index, node in enumerate(self.node_hash):
            if 'if' not in node:
                continue

            last_loop = SyntaxUtils.get_index_array(self.last[index], self.start)

            for key in range(index + 1, last_loop):
                check_column = self.column[index] == self.column[key]
                check_position = self.start[key] < self.last[index]

                if SyntaxUtils.compare_condition(self.node_hash[key]):
                    if check_column and check_position:
                        self.node_if[key] = node
                        self.node_else[index] = self.node_hash[key]
                        self.last[key] = self.last[index]

    def _format_condition_node(self):
        """Find next node after IF block ends"""
        for key, node in enumerate(self.node_hash):
            if SyntaxUtils.compare_condition(node):
                idx = key + 1
                while True:
                    if self.last[key] <= self.start[idx]:
                        self.node_else[key - 1] = self.node_hash[idx + 1]
                        self.node_else[key] = self.node_hash[idx + 1]
                        break
                    idx = idx + 1

        for key, node in enumerate(self.node_hash):
            if SyntaxUtils.compare_condition(node):
                last_else = SyntaxUtils.get_index_array(self.last[key], self.start)
                last_node = self.node_hash[last_else]
                value = last_else

                if SyntaxUtils.compare_condition(last_node):
                    while True:
                        if SyntaxUtils.compare_condition(last_node):
                            last_else = SyntaxUtils.get_index_array(self.last[last_else], self.start)
                            value = last_else - 1
                            last_node = self.node_hash[last_else]
                            break
                        else:
                            else_ = SyntaxUtils.get_index_array(self.last[value], self.start)
                            self.provenance.edge(self.node_hash[else_], last_node)
                            self.visited_x.append(self.node_hash[else_])
                            self.visited_y.append(last_node)
                            self.node_else[else_] = last_node
                            break
                else:
                    self.node_else[value] = last_node
                    else_ = SyntaxUtils.get_index_array(self.last[value], self.start)
                    self.provenance.edge(self.node_hash[else_], last_node)

    def _organize_sequences_if_else(self):
        """Chain together IF → ELIF → ELIF → ELSE sequences"""
        for index, node in enumerate(self.node_hash):
            there_element = self.node_else[index] is not None
            if there_element and 'if' in node and 'else' in str(self.node_else[index]):
                this_item = self.node_hash.index(self.node_else[index]) - 1
                next_item = self.node_hash.index(self.node_else[index])

                while True:
                    if 'else' in self.node_hash[next_item]:
                        node_else = self.node_else[next_item]
                        next_item = self.node_hash.index(node_else)
                    else:
                        self.node_else[this_item] = self.node_hash[next_item]
                        break

    def _update_sequences_if_else(self):
        """Mark nodes with special handling (append '*' marker)"""
        for key, node in enumerate(self.node_hash):
            if 'if' in node and self.node_else[key] is None:
                node_if = SyntaxUtils.get_index_array(self.last[key], self.start)

                if 'else' in self.node_hash[node_if + 1]:
                    self.node_else[key] = '{}*'.format(self.node_else[node_if + 1])
                else:
                    self.node_else[key] = '{}*'.format(self.node_hash[node_if + 1])

    def _get_call_back(self):
        """Create back-edge from last node in loop body → loop header"""
        visited_array = []

        for index in reversed(range(len(self.start))):
            current_node = self.node_hash[index]

            if not SyntaxUtils.compare_loop(current_node):
                continue

            linked_back = SyntaxUtils.get_object_array(self.last[index], self.start)

            if linked_back is not None and self.node_hash[linked_back] not in visited_array:
                self.provenance.edge(
                    self.node_hash[linked_back],
                    current_node,
                    style='dashed'
                )
                visited_array.append(self.node_hash[linked_back])

    def _get_call_ends(self):
        """Create loop exit edges"""
        visited_array = []

        for index, current_node in enumerate(self.node_hash):
            if not SyntaxUtils.compare_loop(current_node):
                continue

            node_loop = SyntaxUtils.get_object_array(self.last[index], self.start)
            node_back = self.node_hash[node_loop]

            if node_back not in visited_array:
                visited_array.append(node_back)
                there_element = self.node_for[node_loop] is not None
                check_element = self.node_for[node_loop] != current_node

                if there_element and check_element:
                    node_next = self.node_for[self._get_return_loop(node_loop)]
                    self.provenance.edge(node_back, node_next, style='dashed')

    def _get_return_loop(self, node_loop):
        """Helper to find loop return point"""
        return node_loop

    def _get_last_loop(self):
        """Handle nested loops - add 'End Loop' edges"""
        for index, item in enumerate(self.node_hash):
            if not SyntaxUtils.compare_loop(item):
                continue

            column_node = self.column[index]

            if self.last[index] not in self.start:
                continue

            last_node = SyntaxUtils.get_index_array(self.last[index], self.start)

            if last_node + 1 == len(self.node_hash):
                last_node -= 1

            if column_node == self.column[last_node + 1]:
                self.node_end_for[index] = self.node_hash[last_node + 1]
                self.provenance.edge(
                    item,
                    self.node_hash[last_node + 1],
                    label=" End Loop"
                )
                self.visited_x.append(self.node_hash[last_node])
                self.visited_y.append(self.node_hash[last_node + 1])
            else:
                index_node = last_node
                while True:
                    if index_node == 0:
                        break
                    else:
                        if SyntaxUtils.compare_loop(self.node_hash[index_node]):
                            check_column = self.column[index_node] < column_node
                            if check_column:
                                self.provenance.edge(
                                    item,
                                    self.node_hash[index_node],
                                    label=" End Loop"
                                )
                                self.node_end_for[index] = self.node_hash[index_node]
                                break
                        index_node = index_node - 1

    def _check_try(self):
        """Find all exception handlers and finally blocks for each try"""
        for index, node in enumerate(self.node_hash):
            if 'try' not in node:
                continue

            try_column = self.column[index]
            try_final = self.last[index]

            for index2 in range(index + 1, len(self.node_hash)):
                if try_final == self.start[index2]:
                    break

                if 'exception' in self.node_hash[index2]:
                    if try_column == self.column[index2]:
                        self.try_except[node].append(self.node_hash[index2])

                elif 'finally' in self.node_hash[index2]:
                    if try_column == self.column[index2]:
                        self.try_except[node].append(self.node_hash[index2])

        for key in self.try_except:
            count = len(self.try_except[key])
            check = False

            if count == 1:
                check = 'finally' in self.try_except[key][0]
            if count == 2:
                check = 'finally' in self.try_except[key][1]

            check_structure = False
            if check:
                element = self.node_hash.index(key)
                last = SyntaxUtils.get_index_array(self.last[element], self.start)
                self.provenance.edge(key, self.try_except[key][1])

                if 'exception' in self.try_except[key][count - 2]:
                    check_structure = True
                    exception_node = self.try_except[key][count - 2]
                    element = self.node_hash.index(exception_node) - 1

                    self.provenance.edge(self.node_hash[element], self.try_except[key][1])
                    self.visited_x.append(self.node_hash[element])

            element = self.node_hash.index(key)
            last = SyntaxUtils.get_index_array(self.last[element], self.start)
            self.provenance.edge(key, self.node_hash[last + 1], style='dashed')

            if check_structure:
                self.visited_y.append(self.node_hash[last + 1])

    def _get_call_try_exception(self):
        """Link try blocks with exception handlers"""
        try:
            for i in range(0, len(self.node_hash) - 1):
                current = self.node_hash[i]
                if 'try' not in current:
                    continue

                intervalo_final = self.last[i]
                intervalo_start = i
                line_exception = -1

                while True:
                    if intervalo_final <= self.start[intervalo_start]:
                        self.node_else[i] = self.node_hash[intervalo_start + 1]
                        break

                    if 'exception' in self.node_hash[intervalo_start]:
                        self.node_if[intervalo_start] = current
                        line_exception = intervalo_start

                    intervalo_start = intervalo_start + 1

                if line_exception != -1:
                    self.node_else[line_exception - 1] = self.node_else[i]
        except:
            print('Error in try/exception linking!')

    def _start_node(self):
        """Create initial 'Start' node"""
        self.node_hash.append('start')
        self.node_else.append(None)
        self.node_if.append(None)
        self.last.append(0)
        self.start.append(0)
        self.column.append(0)
        self.block.append('Start')
        self.type.append('start-code')
        self.hash_index.append(0)
        self.provenance.node('start', label='Start')
        self.generic_hash.append('{}name{}'.format(0, 0))
        return True

    def _create_global_end_node(self):
        """Create final 'End' node"""
        self.node_hash.append('end')
        self.node_else.append(None)
        self.node_if.append(None)
        self.last.append(self.last[-1] + 1)
        self.start.append(self.last[-1] + 1)
        self.column.append(0)
        self.block.append('End')
        self.type.append('end-code')
        self.provenance.node('end', label='End')
        element = '{}{}'.format(self.last[-1] + 1, 0)
        self.hash_index.append(int(element))
        self.generic_hash.append('{}name{}'.format(self.last[-1] + 1, 0))
        return True

    def _create_function_list(self):
        """Initialize def_list and track function scopes"""
        self.def_list = [None for _ in self.node_hash]
        self._limited()

    def _limited(self):
        """Mark all nodes within functions"""
        for index, node in enumerate(self.node_hash):
            if 'function_def' not in node:
                continue

            index_start = index
            index_final = SyntaxUtils.get_index_array(self.last[index], self.start)

            for j in range(index_start, index_final + 1):
                self.def_list[j] = node

    def _create_array_list(self):
        """Initialize tracking arrays"""
        self.node_end_for = [None for _ in self.node_hash]
        self.node_for = [None for _ in self.node_hash]
        self.node_for_sup = [None for _ in self.node_hash]
        self.singleIF = [None for _ in self.node_hash]

    def _create_rules_list(self):
        """Apply all syntax rules"""
        self.syntax_rules_if()
        self.syntax_rules_for()
        self.syntax_rules_try()

    def _format_column(self):
        """Normalize column values for nodes on same line"""
        keys = defaultdict(list)
        for index, item in enumerate(self.start):
            keys[item].append(index)

        for values in keys:
            if len(keys[values]) > 1:
                min_column = self.column[min(keys[values])]
                for element in keys[values]:
                    self.column[element] = min_column

    def _get_point_code(self):
        """Connect Start node to first code node"""
        for index, node in enumerate(self.node_hash):
            if self.def_list[index] is None and 'start' not in node:
                self.provenance.edge('start', node)
                break

    def _create_hash_code(self, x, y, z):
        """Generate hash code for node ID"""
        return '{}{}{}'.format(x, y, z)

    def _arguments_selection(self, start):
        """Get function arguments from database"""
        if self.collector is None:
            return ""
        return self.collector.selection_args(start)

    def create_all_nodes(self, rows):
        """Create all graph nodes from code components"""
        syntax = ConditionNodes()
        mapper = NodeMapper()
        drawer = GraphDrawer(self.provenance)

        self._start_node()

        for codes in rows:
            start_line, final_line, types_line, block_line, colum_line = codes

            nodes_hash = self._create_hash_code(start_line, types_line, final_line)
            label = mapper.get_element('label', start_line, block_line)

            if nodes_hash in self.node_hash:
                continue

            check = False

            if types_line in SyntaxUtils.get_others():
                check, self.provenance = drawer.assign(nodes_hash, label)

            elif types_line == 'class_def':
                self.class_def_name.append(block_line)
                self.class_def_start.append(start_line)
                self.class_def_final.append(final_line)

            elif SyntaxUtils.get_call(types_line, block_line):
                self.call[nodes_hash].append(block_line)
                check, self.provenance = drawer.calls(nodes_hash, label)

            elif types_line == 'import':
                check, self.provenance = drawer.imports(nodes_hash, label)

            elif types_line == 'return':
                check, self.provenance = drawer.calls(nodes_hash, label)

            elif types_line == 'function_def':
                self.defs[nodes_hash].append(block_line)
                args = self._arguments_selection(start_line)
                text = mapper.get_element('function', start_line, block_line, args)
                check, self.provenance = drawer.calls(nodes_hash, text)

            elif types_line in SyntaxUtils.get_loop():
                array = block_line.split('\n')
                condition = syntax.loops(types_line, array[0])
                text = mapper.get_element('label', start_line, types_line)
                check, self.provenance = drawer.loops(nodes_hash, text, condition)

            elif types_line == 'if':
                array = block_line.split('\n')
                if 'elif' in array[0]:
                    nodes_hash = self._create_hash_code(start_line, 'elif', colum_line)
                    text = mapper.get_element('label', start_line, 'elif')
                    check, self.provenance = drawer.condition(
                        nodes_hash, text, syntax.statement_if(array[0])
                    )
                else:
                    text = mapper.get_element('label', start_line, 'if')
                    check, self.provenance = drawer.condition(
                        nodes_hash, text, syntax.statement_if(array[0])
                    )

            elif types_line in SyntaxUtils.get_try() or block_line == 'finally:':
                if types_line == 'try':
                    text = mapper.get_element('label', start_line, 'try')
                    check, self.provenance = drawer.exceptions(nodes_hash, text)
                elif block_line == 'finally:':
                    nodes_hash = self._create_hash_code(start_line, 'finally', colum_line)
                    text = mapper.get_element('label', start_line, 'finally')
                    check, self.provenance = drawer.calls(nodes_hash, text)
                elif types_line == 'exception':
                    text = mapper.get_element('label', start_line, 'except')
                    check, self.provenance = drawer.exceptions(nodes_hash, text)

            elif block_line == 'else:':
                nodes_hash = self._create_hash_code(start_line, 'else', colum_line)
                text = mapper.get_element('label', start_line, 'else')
                check, self.provenance = drawer.calls(nodes_hash, text)

            if check:
                dict_item = {str(colum_line): nodes_hash}
                self.arrayHashing[start_line].append(dict_item)
                generic = '{}name{}'.format(start_line, colum_line)
                element = '{}{}'.format(start_line, colum_line)
                self.hash_index.append(int(element))
                self.generic_hash.append(generic)
                self.block.append(block_line)
                self.last.append(final_line)
                self.start.append(start_line)
                self.column.append(colum_line)
                self.node_else.append(None)
                self.node_if.append(None)
                self.node_hash.append(nodes_hash)
                self.type.append(types_line)

    def _create_function_end_list(self):
        """Track function end points"""
        for i in range(0, len(self.node_hash)):
            if 'function_def' not in self.node_hash[i]:
                continue

            end_index = SyntaxUtils.get_index_array(self.last[i], self.start)
            self.def_function.append(self.node_hash[i])
            self.def_function_final.append(self.node_hash[end_index + 1])
            self.def_function_after.append(self.node_hash[end_index])

    def edge_definition_and_calls(self):
        """Link function calls to their definitions with dashed edges"""
        for key_def in self.defs:
            for key_call in self.call:
                name_def = self.defs[key_def][0]
                name_call = self.call[key_call][0]

                if name_call.find(name_def) != -1:
                    self.provenance.edge(key_call, key_def, style='dashed')

    def _create_elif_list(self):
        """Create elif connection list"""
        for index, node in enumerate(self.node_hash):
            if 'if' not in node and 'elif' not in node:
                continue

            id_node = index
            column = self.column[index]

            for k in range(index + 1, len(self.node_hash)):
                if 'elif' in self.node_hash[k] and column == self.column[k]:
                    self.node_else[id_node] = self.node_hash[k]
                    if self.def_list[id_node] is None:
                        self.provenance.edge(node, self.node_hash[k], label=' False')
                    else:
                        if self.def_list[id_node] == self.def_list[k]:
                            self.provenance.edge(node, self.node_hash[k], label=' False')
                    break

    def _edge_back_in_loops(self):
        """Mark nodes within loops"""
        def return_object(element):
            obj = -1
            for index in range(len(self.start) - 1, -1, -1):
                if element == self.start[index]:
                    obj = index
                    break
            return obj

        for index, item in enumerate(self.node_hash):
            if not SyntaxUtils.compare_loop(item):
                continue

            if self.last[index] in self.start:
                index_loop = return_object(self.last[index])
                for k in range(index, index_loop + 1):
                    self.node_for[k] = item

    def _create_boxes_in_functions(self):
        """Create dashed box boundaries around function bodies"""
        for index, node in enumerate(self.node_hash):
            if 'function_def' not in node:
                continue

            border = SyntaxUtils.get_index_array(self.last[index], self.start)

            cluster_name = 'cluster{}'.format(index)
            with self.provenance.subgraph(name=cluster_name) as subgroup:
                subgroup.attr(style='dashed')

                for index_2 in range(index, border + 1):
                    nodes = self.node_hash[index_2]
                    subgroup.node(nodes)

                    condition = ['for', 'while', 'if', 'elif']
                    if any(x in nodes for x in condition):
                        subgroup.node(nodes + 'c')

    def linking_nodes_graph(self):
        """Create edges between nodes based on control flow"""
        hash_loop = []

        for i in range(1, len(self.node_hash) - 1):
            current = self.node_hash[i]
            next_node = self.node_hash[i + 1]

            visit_x = (current not in self.visited_x)
            visit_y = (next_node not in self.visited_y)
            visit_z = (current not in hash_loop)
            checking = visit_x and visit_y and visit_z

            if not checking:
                continue

            if (('if' not in current) and ('else' not in current) and
                (self.node_else[i] is not None) and (self.node_for[i] is not None)):
                self.provenance.edge(current, self.node_for[i], style="dashed")

            elif current in self.def_function_after:
                continue

            elif 'function_def' in next_node:
                if next_node in self.def_function:
                    index_def_node = self.def_function.index(next_node)
                    self.provenance.edge(current, self.def_function_final[index_def_node])

            elif 'if' in current:
                self.provenance.edge(current, next_node, label='   True')

                if '*' in str(self.node_else[i]):
                    hash_string = self.node_else[i]
                    if self.node_for[i] is not None:
                        item_false = self.node_hash.index(hash_string[0:len(hash_string) - 1])
                        if self.node_for[i] != self.node_for[item_false]:
                            self.provenance.edge(current, self.node_for[i], label='   False')
                        else:
                            self.provenance.edge(
                                current,
                                hash_string[0:len(hash_string) - 1],
                                label='   False'
                            )

            elif 'try' in current:
                self.provenance.edge(current, next_node)

            elif 'exception' in current:
                self.provenance.edge(self.node_if[i], self.node_hash[i])
                self.provenance.edge(current, next_node)

            elif 'else' in current:
                self.provenance.edge(self.node_if[i], self.node_hash[i], label='   False')
                self.provenance.edge(current, next_node)

            elif 'for' in current or 'while' in current:
                self.provenance.edge(current, next_node)

            else:
                if self.node_else[i] is None:
                    self.provenance.edge(current, next_node)
                else:
                    self.provenance.edge(current, self.node_else[i])

        self._create_boxes_in_functions()

    def _verify_function_check(self):
        """Verify and adjust function node_else pointers"""
        for index, node in enumerate(self.node_hash):
            node_else = self.node_else[index]
            node_function = self.def_list[index]
            null_check = node_else is not None and node_function is not None

            if node_else != node_function and null_check:
                self.node_else[index] = node_function

    def component_analyzer(self, collector, rows, data_set):
        """Main orchestration method - builds complete provenance graph"""
        self.collector = collector
        self.create_all_nodes(rows)
        self._create_global_end_node()
        self._format_column()

        self._create_function_list()
        self._create_array_list()
        self._create_rules_list()

        self._create_function_end_list()
        self.edge_definition_and_calls()
        self._create_elif_list()
        self._edge_back_in_loops()

        self._get_point_code()
        self._verify_function_check()
        self.linking_nodes_graph()
