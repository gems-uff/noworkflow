from collections import Counter
from itertools import groupby
import sys

from .save_output import SaveOutput

OPERATIONS = ("add", "sub", "mult", "div", "mod", "pow", "floordiv", # arithmetic operators
              "add_assign", "sub_assign", "mult_assign", "div_assign", # assignment operators 1
              "mod_assign", "pow_assign", "floordiv_assign", # assignment operators 2
              "bitand_assign", "bitor_assign", "bitxor_assign", # assignment operators 3
              "rshift_assign", "lshift_assign", # assignment operators 4
              "eq", "noteq", "gt", "lt", "gte", "lte", # comparison operators
              "and", "or", "not", # logical operators
              "is", "isnot", # identity operators
              "in", "notin", # membership operators
              "bitand", "bitor", "bitxor", "invert", "rshift", "lshift" # bitwise operators
             )


def escape_parentheses(string):
    return string.replace("(", r"\(").replace(")", r"\)")


def entity_name(evaluation):
    component = evaluation.code_component
    ent_name_str = ""
    
    if component.type in ("name", "literal", "param"):
        ent_name_str = str(component.first_char_line) + "_" + component.name
    elif component.type == "subscript":
        ent_name = component.name.split("[")[0]
        ent_name += "@" + component.name.split("[")[1].split("]")[0]
        ent_name_str = str(component.first_char_line) + "_" + ent_name
    else:
        ent_name_str = component.type + str(component.id)
        
    return escape_parentheses(ent_name_str)


def entity_type(evaluation):
    component = evaluation.code_component
    
    if component.type in OPERATIONS:
        return "eval"
    elif component.type == "call":
        return "eval"
    elif component.type == "subscript":
        return "access"
    else:
        return component.type


def is_int(value):
    try:
        int(value)
        return True
    except ValueError:
        return False
        
def is_float(value):
    try:
        float(value)
        return True
    except ValueError:
        return False
        

def export_prov(trial, name="temp", formats="svg"):
    output = SaveOutput(name=name, formats=formats)
    output("prefix script <https://dew-uff.github.io/versioned-prov/ns/script#>")
    output("prefix version <https://dew-uff.github.io/versioned-prov/ns#>\n")
    ckpt_list = []
    assignments = {}
    entity_generated_by_activity = []
    cache = {ev.id: ev for ev in trial.evaluations}

    def insert_ckpt(ckpt):
        if ckpt not in ckpt_list:
            ckpt_list.append(ckpt)
    
    def get_ckpt_order(ckpt):
        return ckpt_list.index(ckpt) + 1
    
    def entity_name_by_id(evaluation_id):
        ev = cache.get(evaluation_id)
        if ev:
            return entity_name(ev)
        return None

    def activity_name(evaluation_id):
        ev = cache.get(evaluation_id)
        if ev:
            return ev.code_component.type
        return None
    
    def activity_label(evaluation_id):
        ev = cache.get(evaluation_id)
        if ev:
            return ev.code_component.name.split("(")[0]
        return None

    def get_ckpt_by_id(evaluation_id):
        ev = cache.get(evaluation_id)
        if ev:
            return ev.checkpoint
        return None

    def find_collection_name(evaluation_id):
        for dep in trial.dependencies:
            if dep.dependent_id == evaluation_id and dep.type == "value":
                dependency = entity_name(dep.dependency)
                if dependency in assignments:
                    dependency = assignments[dependency]  
                return dependency    
        return None

    for act in trial.activations:
        insert_ckpt(act.start_checkpoint)
        
    for ev in trial.evaluations:
        insert_ckpt(ev.checkpoint)
        
    for mem in trial.members:
        insert_ckpt(mem.checkpoint)

    ckpt_list.sort()
    counter = Counter()

    for ev in trial.evaluations:
        if ev.activation_id != 0 and not(ev.code_component.type == "name" and ev.code_component.mode == "r"):
            value = ev.repr
            
            if not is_int(value) and is_float(value):
                value += "f"
            
            entity_str = 'entity({}, [value="{}", type="script:{}"'.format(
                entity_name(ev),
                value,
                entity_type(ev)
            )
            
            if ev.code_component.type == ("literal"):
                entity_str += '])'
            else:
                entity_str += ', label="{}"])'.format(ev.code_component.name)
                
            output(entity_str)
    
    output()

    collection_name = ""
    previous_dep_id = 0
    previous_type = ""
    previous_activity = ""
    sorted_deps = sorted(trial.dependencies, key=lambda x: (x.dependent_id, x.type))
    groups = groupby(sorted_deps, key=lambda x: (x.dependent_id, x.type))
    for (dep_id, type_), group in groups:
        if type_ == "assignment":
            group_list = list(group)
            for dep in group_list:
                key = entity_name(dep.dependent)
                value = entity_name(dep.dependency)
                assignments[key] = value
        elif type_ == "argument" and activity_name(dep_id) != "param":
            act_name = activity_name(dep_id)
            counter[act_name] += 1
            act_type = act_name
            act_label = activity_label(dep_id)
            activity_str = 'activity({}{}, [type="script:{}", label="{}"])'.format(
                act_name, 
                counter[act_name],
                act_type,
                act_label
            )
            output(activity_str)
            previous_activity = act_name + str(counter[act_name])
            
            group_list = list(group)
            for dep in group_list:
                dependency = entity_name(dep.dependency)
                
                if dependency in assignments:
                    dependency = assignments[dependency]
                    
                used_str = 'used({}{}, {}, -,[version:checkpoint="{}"])'.format(
                    act_name, 
                    counter[act_name],
                    dependency,
                    get_ckpt_order(dep.dependency.checkpoint)
                )
                output(used_str)
                
            ent_act = entity_name_by_id(dep_id) + act_name + str(counter[act_name])
            if ent_act not in entity_generated_by_activity:
                wasGeneratedBy_str = 'wasGeneratedBy({}, {}{}, -,[version:checkpoint="{}"])'.format(
                    entity_name_by_id(dep_id),
                    act_name, 
                    counter[act_name],
                    get_ckpt_order(get_ckpt_by_id(dep_id))
                )
                output(wasGeneratedBy_str)
            
            output()
        elif type_ == "value" or type_ == "slice":
            group_list = list(group)
            for dep in group_list:
                using_activity = previous_activity
                
                if type_ == "value" and not(previous_dep_id == dep_id and previous_type == "assign"):
                    using_activity = "access" + str(counter["access"] + 1)
                    previous_activity = using_activity
                    
                dependency = entity_name(dep.dependency)
                
                if dependency in assignments:
                    dependency = assignments[dependency]
                    
                used_str = 'used({}, {}, -'.format(
                    using_activity,
                    dependency
                )
                
                if type_ == "value":
                    used_str += ', [version:checkpoint="{}"]'.format(
                        get_ckpt_order(dep.dependency.checkpoint)
                    )
                    collection_name = dependency
                    
                used_str += ')'
                output(used_str)
        elif type_ != "item" and type_ != "dependency":
            counter["g"] += 1
            act_name = type_
            act_type = type_
            
            if type_ == "use":
                act_name = activity_name(dep_id)
                
                if act_name in OPERATIONS:
                    act_type = "operation"
            elif type_ in OPERATIONS:
                act_type = "operation"
            
            if act_type != "use":
                counter[act_name] += 1
                activity_str = 'activity({}{}, [type="script:{}"])'.format(
                    act_name, 
                    counter[act_name],
                    act_type
                )
                output(activity_str)
                previous_activity = act_name + str(counter[act_name])

            group_list = list(group)
            for dep in group_list:
                counter["u"] += 1
                dependent = entity_name(dep.dependent)
                dependency = entity_name(dep.dependency)
                count_act_name = counter[act_name]
                
                if dependency in assignments:
                    dependency = assignments[dependency]
                
                if act_name == "call" and act_type == "use":
                    count_act_name = counter[act_name] + 1
                    entity_generated_by_activity.append(dependent + "call" + str(count_act_name))
                
                wasDerivedFrom_str = 'wasDerivedFrom({}, {}, {}{}, g{}, u{}, ['.format(
                    dependent,
                    dependency,
                    act_name,
                    count_act_name,
                    counter["g"],
                    counter["u"],
                )

                if dep.reference == 1:
                    wasDerivedFrom_str += 'type="version:Reference", '

                wasDerivedFrom_str += 'version:checkpoint="{}"'.format(
                    get_ckpt_order(dep.dependent.checkpoint)
                )
                
                if type_ == "access":
                    wasDerivedFrom_str += ', version:collection="{}", version:key="{}", version:access="{}"'.format(
                        collection_name,
                        dep.key[1:-1],
                        dep.dependent.code_component.mode
                    )
                elif entity_type(dep.dependent) == "access":
                    wasDerivedFrom_str += ', version:collection="{}", version:key="{}", version:access="{}"'.format(
                        find_collection_name(dep.dependent_id),
                        entity_name(dep.dependent).split("@")[1],
                        "w"
                    )
                
                wasDerivedFrom_str += '])'
                output(wasDerivedFrom_str)
            
            output()
        
        previous_dep_id = dep_id
        previous_type = type_

    for mem in trial.members:
        if mem.collection_activation_id and mem.member_activation_id:        
            member = entity_name(mem.member)
                
            if member in assignments:
                member = assignments[member]
                    
            hadMember_str = 'hadMember({}, {}, [type="version:Put", version:key="{}", version:checkpoint="{}"])'.format(
                entity_name(mem.collection),
                member,
                mem.key[1:-1],
                get_ckpt_order(mem.checkpoint)
            )
            output(hadMember_str)

    # TODO: Check new models
    # if trial.experiment:
    #     exp = trial.experiment
    #     exp_entity = 'entity(experiment_{}, [type="script:experiment", label="{}", description="{}"])'.format(
    #         exp.id, exp.name, exp.description or ""
    #     )
    #     output(exp_entity)
    
    if trial.user:
        user = trial.user
        user_entity = 'entity(user_{}, [type="script:user", label="{}"])'.format(
            user.id, user.userLogin
        )
        output(user_entity)
    
        for group in trial.user.groups:
            group_entity = 'entity(group_{}, [type="script:group", label="{}"])'.format(
                group.id, group.name
            )
            output(group_entity)
        
        for member_of_group in trial.user.member_of_groups:
            member_entity = 'entity(memberOfGroup_{}, [type="script:memberOfGroup", userId="{}", groupId="{}"])'.format(
                member_of_group.id, member_of_group.userId, member_of_group.groupId
            )
            output(member_entity)
    
    for annotation in trial.extended_annotations:
        annotation_entity = 'entity(extendedAnnotation_{}, [type="script:extendedAnnotation", annotation="{}", description="{}", annotationFormat="{}", provenanceType="{}", annotationLevel="{}", relatedExperiment="{}", relatedTrial="{}"])'.format(
            annotation.id, annotation.annotation or "", annotation.description or "",
            annotation.annotationFormat or "", annotation.provenanceType or "",
            annotation.annotationLevel or "", annotation.relatedExperiment or "",
            annotation.relatedTrial or ""
        )
        output(annotation_entity)

    return output
