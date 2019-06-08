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
from ..utils.collab import exportBundle



from ..persistence.lightweight import ObjectStore, SharedObjectStore
from ..persistence.lightweight import ActivationLW,ArgumentLW,CodeBlockLW,CodeComponentLW,CompositionLW,DependencyLW,EnvironmentAttrLW
from ..persistence.lightweight import EvaluationLW,FileAccessLW,MemberLW,ModuleLW,TrialLW

from ..persistence.models import Trial,Activation,Argument,CodeBlock,CodeComponent,Composition,Dependency,EnvironmentAttr,Evaluation
from ..persistence.models import FileAccess,Member,Module,Tag

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

        bundle=exportBundle(trialsToImportIds)
       
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


        [trials_store.add_from_object(x) for x in bundle.trials]
        [codeBlock_store.add_from_object(x) for x in bundle.codeBlocks]
        [arguments_store.add_from_object(x) for x in bundle.arguments]
        [codeComponent_store.add_from_object(x) for x in bundle.codeComponents]
        [activation_store.add_from_object(x) for x in bundle.activations]
        [composition_store.add_from_object(x) for x in bundle.compositions]
        [dependency_store.add_from_object(x) for x in bundle.dependencies]
        [env_store.add_from_object(x) for x in bundle.environmentAttrs]
        [evaluation_store.add_from_object(x) for x in bundle.evaluations]
        [fileAccess_store.add_from_object(x) for x in bundle.fileAccesses]
        [member_store.add_from_object(x) for x in bundle.members]
        [module_store.add_from_object(x) for x in bundle.modules]

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

        for x in trialsToImport:
            main_block=[c for c in bundle.codeBlocks if c.trial_id==x.id and x.main_id==c.id]
            main_block=main_block[0]
            Tag.create_automatic_tag(x.id,main_block.code_hash,x.command)

        print("Finish importing")
       



