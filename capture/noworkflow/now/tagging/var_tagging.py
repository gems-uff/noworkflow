
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
import ipdb

class NotebookQuerierOptions(QuerierOptions):
    import numpy as np
    global body_function_def
    dep_list = []
    
    def __init__(self, level, *args, **kwargs):
        QuerierOptions.__init__(self, *args, **kwargs) # change it to super when integrating in the main code
        self.level = level
    
    def visit_arrow(self, context, neighbor):
        import numpy as np
        # keeping 
        if neighbor.evaluation.code_component.type == 'function_def':
            body_function_def.append(int(neighbor.evaluation.code_component.id))
       
        arrow_list = ('argument', '<.__class__>', 'item')
        type_list = ('add', 'literal', 'mult', 'div', 'param', 'sub', 'attribute', 'usub', 'function_def')
        
        context_code_comp = context.evaluation.code_component
        neighbor_code_comp = neighbor.evaluation.code_component
        
        if context_code_comp.type == 'literal' and neighbor_code_comp:
            self.dep_list.append(( context_code_comp.name, context.evaluation.repr))
        elif neighbor.arrow not in arrow_list:
                if context_code_comp.type not in type_list:
                    if neighbor_code_comp.type not in type_list:
                        if not (neighbor.arrow == 'use' and context_code_comp.type == 'call'):
                            if (neighbor_code_comp.container_id != None):
                                if neighbor_code_comp.container_id not in body_function_def or self.level:
                                    #ipdb.set_trace()
                                    if len(context.evaluation.repr) > 20:  # arbitrary lenght to avoid matricial outputs
                                        dimensions = np.frombuffer(context.evaluation.repr.encode(), dtype=np.uint8)
                                        self.dep_list.append((str(context_code_comp.name), str('matrix dim' + str(dimensions.shape))))
                                    else:
                                        self.dep_list.append((str(context_code_comp.name), str(context.evaluation.repr)))

    def predecessors_output(self):
        global dep_dict
        
        # remove duplicated keys. No better solution up to now 
        unique_elements = []
        seen_elements = set()

        for element in self.dep_list:
            if element not in seen_elements:
                unique_elements.append(element)
                seen_elements.add(element)     
        
        # remove duplicated values
        elements = [tuple_ for tuple_ in unique_elements if tuple_[0] != tuple_[1]]

        # create an enumerated dictionary        
        dep_dict = {i[0] : i[1] for i in reversed(list(enumerate(elements)))}
        return dep_dict, self.dep_list

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

def dict_to_text(op_dict):
    import textwrap

    # Convert dictionary to plain text with each key-value pair on a separate row
    plain_text = ""
    
    for key, value_list in op_dict.items():
        values_text = ", ".join(map(str, value_list))
        key_value_pair = f"{values_text}"
        wrapped_lines = textwrap.fill(key_value_pair, subsequent_indent='    ')
        plain_text += wrapped_lines + "\n"

    return plain_text

def exp_compare(trial_a, trial_b, html=False):
    import shelve
    import difflib
    from IPython.display import HTML
    
    # Retrieve the ops dictionary from the shelve file
    with shelve.open('ops') as shelf:
        dict1 = shelf[trial_a]
        dict2 = shelf[trial_b]
    
    if not html:
        return dict1, dict2
    else:
        plain_text_a = dict_to_text(dict1)
        plain_text_b = dict_to_text(dict2)

        # Original and modified code strings
        original_code = plain_text_a
        modified_code = plain_text_b

        # Calculate the differences using difflib
        differ = difflib.HtmlDiff()
        diff_html = differ.make_table(
            original_code.splitlines(),
            modified_code.splitlines(),
            context=False,  # Show some context lines around changes
            numlines=0     # Number of lines of context to show
        )

        # Add CSS styling for left alignment
        styled_diff_html = f'''
        <style>
        .diff_header {{
            background-color: #f1f1f1;
        }}
        .diff_next {{
            background-color: #f1f1f1;
        }}
        .diff_add {{
            background-color: #ddffdd;
        }}
        .diff_chg {{
            background-color: #ffffaa;
        }}
        .diff_sub {{
            background-color: #ffdddd;
        }}
        .diff_table {{
            text-align: left; /* Align the table content to the left */
        }}
        </style>
        {diff_html}
        '''

        # Display the styled HTML in a Jupyter Notebook cell
        display(HTML(styled_diff_html))
       
        #display(HTML(diff_html))

def store_operations(trial, ops_dict):
    import shelve

    # Store the dictionary in a shelve file
    with shelve.open('ops') as shelf:
        shelf[trial] = ops_dict
        print("Dictionary stored in shelve.")
        

def get_pre_all(glanularity = False):
    from noworkflow.now.persistence.models.stage_tags import StageTags
    from noworkflow.now.persistence import relational
    from noworkflow.now.persistence.models.base import proxy_gen

    global tagged_var_dict
    
    all_tags = {}
    for key in tagged_var_dict:
        all_tags[key] = get_pre(key, glanularity)
        
    return all_tags

def tagged_comp(tag_name):
    from noworkflow.now.persistence.models.base import proxy_gen
    from noworkflow.now.persistence import relational

    access_list = list(proxy_gen(relational.session.query(StageTags.m).filter(StageTags.m.name == tag_name)))
    
    values_list = []
    for i in access_list:
        values_list.append([i.trial_id, i.trial_id[-5:],  i.name, float(i.tag_name)])
        
    return values_list

def plot_comp(tag_name = 'roc_rf'):
    import pandas as pd
    from noworkflow.now.persistence.models.base import proxy_gen
    from noworkflow.now.persistence import relational
    from noworkflow.now.persistence.lightweight import StageTags

    import matplotlib.pyplot as plt

    access_list = list(proxy_gen(relational.session.query(StageTags.m).filter(StageTags.m.name == tag_name)))
    
    values_list = []
    for i in access_list:
        values_list.append([i.trial_id, i.trial_id[-5:],  i.name, float(i.tag_name)])
    
    columns = ['trial_id', 'short_trial_id',  'tag', 'value']
    df = pd.DataFrame(values_list, columns=columns)
    
    df = df.tail(30) # arbitrary cuttoff for better chart visualization
    
    plt.bar(df.short_trial_id, df.value)
    plt.title(tag_name + ' values')
    plt.xticks(rotation=90)

    plt.show()