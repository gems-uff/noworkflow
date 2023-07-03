# Copyright (c) 2016 Universidade Federal Fluminense (UFF)
# Copyright (c) 2016 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""Lightweight Bundle"""


from ..models import CodeBlock
from .. import content

from . import ActivationLW,ArgumentLW,CodeBlockLW,CodeComponentLW,CompositionLW,DependencyLW,EnvironmentAttrLW
from . import EvaluationLW,FileAccessLW,CellTagsLW,MemberLW,ModuleLW,TrialLW, UserLW

from .base import BaseLW, define_attrs
from datetime import datetime

class BundleLW(BaseLW):
    """Bundle lightweight object"""
    def __init__(self):
        self.trials=[]
        self.activations=[]
        self.arguments=[]
        self.codeBlocks=[]
        self.codeComponents=[]
        self.compositions=[]
        self.dependencies=[]
        self.environmentAttrs=[]
        self.evaluations=[]
        self.fileAccesses=[]
        self.members=[]
        self.modules=[]
        self.users=[]
        
    def __json__(self):
        return {
            'trials':   [x.__json__() for x in self.trials],
            'activations': [x.__json__() for x in self.activations],
            'arguments': [x.__json__() for x in self.arguments],
            'codeBlocks': [x.__json__() for x in self.codeBlocks],
            'codeComponents': [x.__json__() for x in self.codeComponents],
            'compositions': [x.__json__() for x in self.compositions],
            'dependencies': [x.__json__() for x in self.dependencies],
            'environmentAttrs': [x.__json__() for x in self.environmentAttrs],
            'evaluations': [x.__json__() for x in self.evaluations],
            'fileAccesses': [x.__json__() for x in self.fileAccesses],
            'members': [x.__json__() for x in self.members],
            'modules': [x.__json__() for x in self.modules],
            'users': [x.__json__() for x in self.users]
        }
    def returnDateTimeInfo(self,finish):
        resp=finish
        if finish is not None:
            resp=datetime.strptime(finish, '%Y-%m-%d %H:%M:%S.%f')
        return resp
    def from_json(self, data):
        self.trials.extend([TrialLW(x["id"],x["script"],\
            self.returnDateTimeInfo(x["start"]),self.returnDateTimeInfo(x["finish"]),\
            x["command"],x["path"],x["status"],\
            x["modules_inherited_from_trial_id"],x["parent_id"],x["main_id"],x["experiment_id"],x["user_id"]) for x in data["trials"]])
     
        self.activations=[ActivationLW(x,x["trial_id"],x["name"],x["start_checkpoint"],x["code_block_id"],x["id"]) for x in data["activations"]]
        self.arguments=[ArgumentLW(x["id"],x["trial_id"],x["name"],x["value"]) for x in data["arguments"]]
        self.codeBlocks=[CodeBlockLW(id_=x["id"],trial_id=x["trial_id"],code=x["code_hash"],binary=False,docstring=x["docstring"],code_hash=x["code_hash"], filename=None) for x in data["codeBlocks"]]
        self.codeComponents=[CodeComponentLW(x["id"],x["trial_id"],x["name"],x["type"],x["mode"],x["first_char_line"], x["first_char_column"], \
            x["last_char_line"],x["last_char_column"],x["container_id"]) for x in data["codeComponents"]]
        self.compositions=[CompositionLW(x["id"],x["trial_id"],x["part_id"],\
            x["whole_id"],x["type"],x["position"],x["extra"]) for x in data["compositions"]]
        self.dependencies=[DependencyLW(x["id"],x["trial_id"],x["dependent_activation_id"],x["dependent_id"],x["dependency_activation_id"],\
            x["dependency_id"],x["type"],x["reference"],x["collection_activation_id"],x["collection_id"],x["key"]) for x in data["dependencies"]]
        self.environmentAttrs=[EnvironmentAttrLW(x["id"],x["trial_id"],x["name"],x["value"]) for x in data["environmentAttrs"]]
        self.evaluations= [EvaluationLW(x["id"],x["trial_id"],x["code_component_id"],x["activation_id"],x["checkpoint"],x["repr"]) for x in data["evaluations"]]
        self.fileAccesses=[FileAccessLW(x["id"],x["trial_id"],x["name"],x["checkpoint"],x["mode"],x["buffering"],\
            x["content_hash_before"],x["content_hash_after"],x["activation_id"]) for x in data["fileAccesses"]]
        self.fileAccesses=[CellTagsLW(x["id"],x["trial_id"],x["name"],x["checkpoint"],x["mode"],x["buffering"],\
            x["content_hash_before"],x["content_hash_after"],x["activation_id"]) for x in data["fileAccesses"]]
        self.members=[MemberLW(x["id"],x["trial_id"],x["collection_activation_id"],x["collection_id"],x["member_activation_id"],\
            x["member_id"],x["key"],x["checkpoint"],x["type"]) for x in data["members"]]
        self.modules=[ModuleLW(x["id"],x["trial_id"],x["name"],x["version"],x["path"],x["code_block_id"],x["transformed"]) for x in data["modules"]]
        self.users=[UserLW(x["id"],x["userLogin"]) for x in data["users"]]
  
