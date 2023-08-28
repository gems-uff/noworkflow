
# Copyright (c) 2016 Universidade Federal Fluminense (UFF)
# Copyright (c) 2016 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""Variable tagging"""
from __future__ import (absolute_import, print_function,
                        division, unicode_literals)

from noworkflow.now.persistence.models import Evaluation
from noworkflow.now.models.dependency_querier import DependencyQuerier
from noworkflow.now.models.dependency_querier.querier_options import QuerierOptions

class NotebookQuerierOptions(QuerierOptions):
    global body_function_def
    dep_list = []
    
    def __init__(self, level, *args, **kwargs):
        QuerierOptions.__init__(self, *args, **kwargs) # change it to super when integrating in the main code
        self.level = level
    
    def visit_arrow(self, context, neighbor):
        # keeping 
        if neighbor.evaluation.code_component.type == 'function_def':
            body_function_def.append(int(neighbor.evaluation.code_component.id))
       
        arrow_list = ('argument', '<.__class__>', 'item')
        type_list = ('add', 'literal', 'mult', 'div', 'param', 'sub', 'attribute', 'usub', 'function_def')
        
        context_code_comp = context.evaluation.code_component
        neighbor_code_comp = neighbor.evaluation.code_component
        
        if context_code_comp.type == 'literal' and neighbor_code_comp.type == 'type':
            self.dep_list.append((str(context.evaluation.checkpoint), str(context.evaluation.id), context_code_comp.name, context.evaluation.repr))
        elif neighbor.arrow not in arrow_list:
                if context_code_comp.type not in type_list:
                    if neighbor_code_comp.type not in type_list:
                        if not (neighbor.arrow == 'use' and context_code_comp.type == 'call'):
                            if (neighbor_code_comp.container_id != None):
                                if neighbor_code_comp.container_id not in body_function_def or self.level:
                                    #if len(context.evaluation.repr) > 0:  # arbitrary lenght to avoid matricial outputs
                                    self.dep_list.append((str(context.evaluation.checkpoint), str(context.evaluation.id), context_code_comp.name, context.evaluation.repr))
                                    #else:
                                    #    self.dep_list.append((str(context.evaluation.checkpoint), str(context.evaluation.id), context_code_comp.name, 'matrix'))

    def predecessors_output(self):
        global dep_dict
        
        dep_dict = {i[0] : i[1] for i in enumerate(self.dep_list)}
        return dep_dict

def now_tag(tag):
   """Tags a given cell"""
   
   trial_id = __noworkflow__.trial_id
   name = __noworkflow__.last_activation.name
   tag_name = str(tag)
   activation_id = __noworkflow__.last_activation.evaluation.activation_id

   # Writing it
   __noworkflow__.stage_tagss.add(trial_id, name, tag_name, activation_id)

def now_variable(var_name, value):
   """Tag a given variable"""
   global tagged_var_dict
       
   dependencies = __noworkflow__.last_activation.dependencies[-1]
   dep_evaluation = dependencies.dependencies[-1].evaluation
    
   trial_id = dep_evaluation.trial_id
   name = str(var_name)
   activation_id = dep_evaluation.activation_id
      
   tagged_var_dict[name] = [dep_evaluation.id, value, activation_id, trial_id] 
   
   print(dep_evaluation)

  # Writing it
   __noworkflow__.stage_tagss.add(trial_id, name, value, activation_id)
    
   return value   

    
def get_pre(var_name, glanularity = False):
    global tagged_var_dict
    global nbOptions
    global dep_dict

    # Get an Evaluation
    evaluation_id =  tagged_var_dict[var_name][0]
    trial_id =  tagged_var_dict[var_name][3]
    evals = Evaluation((trial_id, evaluation_id))
    
    nbOptions = NotebookQuerierOptions(level = glanularity)
    querier = DependencyQuerier(options=nbOptions)
    _, _, _ = querier.navigate_dependencies([evals])  
    
    return nbOptions.predecessors_output()   

def exp_compare(trial_a, trial_b):
    import shelve
    
    # Retrieve the dictionary a from the shelve file
    with shelve.open('ops') as shelf:
        dict_a = shelf['dict_a']
        print("Retrieved dictionary:", dict_a)
        dict_b = shelf['dict_b']
        print("Retrieved dictionary:", dict_b)
        
    # comparing two dicts
    
    return dict_a == dict_b

def store_operations(trial, ops_dict):
    import shelve

    # Store the dictionary in a shelve file
    with shelve.open('ops') as shelf:
        shelf[trial] = ops_dict
        print("Dictionary stored in shelve.")
        
def exp_compare(trial_a, trial_b):
    import shelve
    
    # Retrieve the ops dictionary from the shelve file
    with shelve.open('ops') as shelf:
        dict1 = shelf[trial_a]
        dict2 = shelf[trial_b]
        
    # Compare dictionaries' specific indices and print the results
    
    if len(dict1) == len(dict2):
        print(f"Pipelines have same lenght")
    else:
        print(f"Pipelines A and B differ in lenght")


    # comparing two dicts
    common_keys = set(dict1.keys()) & set(dict2.keys())
    indices_to_compare = [2, 3]
   
    for key in common_keys:
        values1 = dict1.get(key, [])
        values2 = dict2.get(key, [])
        
        #compare_length = min(len(values1), len(values2), max(indices_to_compare) + 1)
        
        are_equal = all(values1[idx] == values2[idx] for idx in indices_to_compare)
        
        if are_equal:
            print(f"Key '{key}': Values are equal")
        else:
            print(f"Key '{key}': Values are different")
            print("->>>", values1[2:4], values2[2:4])

def get_pre_all(glanularity = False):
    from noworkflow.now.persistence.models.stage_tags import StageTags
    from noworkflow.now.persistence import relational
    from noworkflow.now.persistence.models.base import proxy_gen

    global tagged_var_dict
    
    #tagged_values = list(proxy_gen(relational.session.query(StageTags.m).filter(StageTags.m.trial_id == __noworkflow__.trial_id)))
    all_tags = {}
    for key in tagged_var_dict:
        all_tags[key] = get_pre(key, glanularity)
        
    return all_tags