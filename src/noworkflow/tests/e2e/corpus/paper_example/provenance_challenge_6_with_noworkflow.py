import os

from sqlalchemy import create_engine, MetaData, Table
from sqlalchemy.orm import mapper, Session
from noworkflow.now.persistence import persistence_config, relational
from noworkflow.now.persistence.models import Trial, Evaluation, CodeComponent, Dependency, Tag
from noworkflow.now.models.dependency_graph.filters import FilterWasDerivedFrom

def get_database():
    persistence_config.connect(os.getcwd())
    return relational.session

def get_trials(session):
    return session.query(Trial.m).all()

def get_evaluations(session, trial_id):
    evaluations_query = session.query(Evaluation.m, CodeComponent.m.name, CodeComponent.m.first_char_line).filter(
            Evaluation.m.trial_id==trial_id, 
            Evaluation.m.code_component_id == CodeComponent.m.id, 
            CodeComponent.m.trial_id == trial_id).all()
    
    return evaluations_query

def get_evaluation_wdf(trial_id, evaluation_id):
    evaluation_id = str(evaluation_id)
    return FilterWasDerivedFrom(evaluation_id, trial_id).was_derived_from_list

def get_precedent_evaluation(evaluation_wdf, session):
    for evaluation in evaluation_wdf:
        evaluation_name = session.query(CodeComponent.m.name).filter(CodeComponent.m.trial_id == evaluation.trial_id, CodeComponent.m.id == evaluation.code_component_id).all()[0][0]
        if "train_test_split(" in evaluation_name: #the function G is train_test_split in our case.
            #print("Found G: ", evaluation_name)
            return evaluation
        
def get_evaluation_dependency(session, trial_id, evaluation_id):
    return session.query(Dependency.m).filter(Dependency.m.trial_id==trial_id, Dependency.m.dependent_id==evaluation_id, Dependency.m.type=="argument").all() # Dependency.type == "argument" OK
    

session = get_database()
trials = get_trials(session)
for trial in trials:
    this_trial_evaluations = get_evaluations(session, trial.id)
    for evaluation in this_trial_evaluations:
        
        #Find F in the trial
        if("f1_score(" in (evaluation[1])): #and evaluation[2]== 36): # F is 'f1_score' in our case. F's code_line is '36'
            #print("Found F: ", evaluation[1])
            evaluation_wdf = get_evaluation_wdf(trial.id, evaluation[0].id)
            #Find G in F wdf
            precedent_evaluation = get_precedent_evaluation(evaluation_wdf, session)
            precedent_evaluation_dependency = get_evaluation_dependency(session, trial.id, precedent_evaluation.id)
            #Find if function G had P as parameter
            for dependency in precedent_evaluation_dependency:
                dependency_as_evaluation = session.query(Evaluation.m).filter(Evaluation.m.id==dependency.dependency_id, Evaluation.m.trial_id==trial.id).all()[0]
                argument_string = dependency_as_evaluation.repr
                if(argument_string == "42"): # P is 42 in our case
                    # F's trial
                    f_trial_tag = session.query(Tag.m).filter(Tag.m.trial_id==evaluation[0].trial_id).all()[0]
                    print("Trial tag: ", f_trial_tag.name)
                    #print("Found: " + argument_string)
                    
                    #F output
                    print("Output of f1_score: ", evaluation[0].repr)