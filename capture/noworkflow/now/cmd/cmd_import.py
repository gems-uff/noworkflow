# Copyright (c) 2016 Universidade Federal Fluminense (UFF)
# Copyright (c) 2016 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
""""now list" command"""
from __future__ import (absolute_import, print_function,
                        division, unicode_literals)

import os
import shutil
from functools import reduce

from ..persistence.config import PersistenceConfig
from ..persistence.content_database import ContentDatabase
from ..persistence.relational_database import RelationalDatabase
from ..persistence import persistence_config, relational


from ..persistence.lightweight import ObjectStore, SharedObjectStore
from ..persistence.lightweight import ActivationLW,ArgumentLW,CodeBlockLW,CodeComponentLW,CompositionLW,DependencyLW,EnvironmentAttrLW
from ..persistence.lightweight import EvaluationLW,FileAccessLW,MemberLW,ModuleLW,TrialLW

from ..persistence.models import Trial,Activation,Argument,CodeBlock,CodeComponent,Composition,Dependency,EnvironmentAttr,Evaluation
from ..persistence.models import FileAccess,Member,Module

from .command import Command


class Import(Command):
    """Import trials to a database"""
    def __init__(self, *args, **kwargs):
        super(Import, self).__init__(*args, **kwargs)
        self.targetContent=None
        self.sourceContent=None

        self.targetRelational=None
        self.sourceRelational=None

    def add_arguments(self):
        add_arg = self.add_argument
        add_arg("--target", type=str,
                help="set project path where is the target database. Default to "
                     "current directory")
        add_arg("--source", type=str,
                help="set absolute project path where is the database to import.")
        add_arg("--label", type=str,
                help="optional label for the import.")

    def import_content(self,args):
        
        targetFiles=self.targetContent.listAll()
        sourceFiles=self.sourceContent.listAll()
        
        [self.addFile(x) for x in sourceFiles if x not in targetFiles]
    
    def addFile(self,name):
        content=self.sourceContent.get(name)
        self.targetContent.put(content)

    def populate(self,args):
        if not (args.source):  
            raise ValueError("--source can't be empty")  
        
        sourceConfig=PersistenceConfig()  
        
        self.sourceContent=ContentDatabase(sourceConfig)  
        sourceConfig.connect_existing(args.source)

        targetConfig=PersistenceConfig()  

        self.targetContent=ContentDatabase(targetConfig) 
        targetConfig.connect(args.target or os.getcwd())


    def execute(self, args):

        self.populate(args)
            
        self.import_content(args)
             
        print("Load Trials")
        persistence_config.connect(args.target or os.getcwd())
        targetTrials=[t for t in Trial.all()]
       
        persistence_config.connect(args.source)
        sourceTrials=[t for t in Trial.all()]
        
        targetUuids=[x.id for x in targetTrials]
        trialsToImport=[x for x in sourceTrials if x.id not in targetUuids]
        trialsToImportIds=[x.id for x in trialsToImport]

        print("Load dependencies")
        
        actvsToImport=Activation.load_by_trials(trialsToImportIds)
        argsToImport=Argument.load_by_trials(trialsToImportIds)
        codeBlockToImport=CodeBlock.load_by_trials(trialsToImportIds)
        codeComponentToImport=CodeComponent.load_by_trials(trialsToImportIds)
        compositionToImport=Composition.load_by_trials(trialsToImportIds)
        dependencyToImport=Dependency.load_by_trials(trialsToImportIds)
        envToImport=EnvironmentAttr.load_by_trials(trialsToImportIds)
        evaluationToImport=Evaluation.load_by_trials(trialsToImportIds)
        fileAccessToImport=FileAccess.load_by_trials(trialsToImportIds)
        memberToImport=Member.load_by_trials(trialsToImportIds)
        moduleToImport=Module.load_by_trials(trialsToImportIds)
        print("Finish Load dependencies")

        
        persistence_config.connect(args.target or os.getcwd())

        
        print("Preparing Stores")
        trials_store=ObjectStore(TrialLW)
        codeBlock_store=ObjectStore(CodeBlockLW)
        arguments_store=ObjectStore(ArgumentLW)
        codeComponent_store=ObjectStore(CodeComponentLW)
        activation_store=ObjectStore(ActivationLW)
        composition_store=ObjectStore(CompositionLW)
        dependency_store=ObjectStore(DependencyLW)
        env_store=ObjectStore(EnvironmentAttrLW)
        evaluation_store=ObjectStore(EvaluationLW)
        fileAccess_store=ObjectStore(FileAccessLW)
        member_store=ObjectStore(MemberLW)
        module_store=ObjectStore(ModuleLW)

        [trials_store.add_explicit_id(x.id,x.script,x.start,x.finish,x.command,x.path,x.status,x.modules_inherited_from_trial_id,\
            x.parent_id,x.main_id) for x in trialsToImport]
        [arguments_store.add_explicit_id(x.id,x.trial_id,x.name,x.value) for x in argsToImport]
        [codeBlock_store.add_explicit_id(x.id,x.trial_id,x.code_hash,False,x.docstring) for x in codeBlockToImport]
        [codeComponent_store.add_explicit_id(x.id,x.trial_id,x.name,x.type,x.mode,x.first_char_line, \
            x.first_char_column,x.last_char_line,x.last_char_column,x.container_id) for x in codeComponentToImport]
        [activation_store.add_explicit_id(x,x.trial_id,x.name,x.start_checkpoint,x.code_block_id) for x in actvsToImport]
        [composition_store.add_explicit_id(x.id,x.trial_id,x.part_id,x.whole_id,x.type,x.position,x.extra) for x in compositionToImport]
        [dependency_store.add_explicit_id(x.id,x.trial_id,x.dependent_activation_id,x.dependent_id,x.dependency_activation_id,x.dependency_id,\
            x.type,x.reference,x.collection_activation_id,x.collection_id,x.key) for x in dependencyToImport]
        [env_store.add_explicit_id(x.id,x.trial_id,x.name,x.value) for x in envToImport]
        [evaluation_store.add_explicit_id(x.id,x.trial_id,x.code_component_id,x.activation_id,x.checkpoint,x.repr) for x in evaluationToImport]
        [fileAccess_store.add_explicit_id(x.id,x.trial_id,x.name,x.checkpoint,x.mode,x.buffering,\
            x.content_hash_before,x.content_hash_after,x.activation_id) for x in fileAccessToImport]
        [member_store.add_explicit_id(x.id,x.trial_id,x.collection_activation_id,x.collection_id,x.member_activation_id,\
            x.member_id,x.key,x.checkpoint,x.type) for x in memberToImport]
        [module_store.add_explicit_id(x.id,x.trial_id,x.name,x.version,x.path,x.code_block_id,x.transformed) for x in moduleToImport]

        print("Saving Stores")
        trials_store.do_store()
        arguments_store.do_store()
        codeBlock_store.do_store()
        codeComponent_store.do_store()
        activation_store.do_store()
        composition_store.do_store()
        dependency_store.do_store()
        env_store.do_store()
        evaluation_store.do_store()
        fileAccess_store.do_store()
        member_store.do_store()
        module_store.do_store()


        print("Finish importing")
       



