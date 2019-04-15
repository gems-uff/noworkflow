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
from ..persistence.models import Trial
from ..persistence import persistence_config, relational

from .command import Command
from ..persistence.models import Trial

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
        print("Add file: "+name)
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


    def insertTrial(self,source):

        source.newId=Trial.createImport( source.uuid, source.script, 
            source.start, source.finish, source.command,
            source.path,source.status)

    def execute(self, args):

        self.populate(args)
            
        self.import_content(args)
             

        persistence_config.connect(args.target or os.getcwd())
        targetTrials=[t for t in Trial.all()]
       
        persistence_config.connect(args.source)
        sourceTrials=[t for t in Trial.all()]
        
        targetUuids=[x.uuid for x in targetTrials]
        trialsToImport=[x for x in sourceTrials if x.uuid not in targetUuids]

        persistence_config.connect(args.target or os.getcwd())
        [self.insertTrial(x) for x in trialsToImport]
        [print(x.id) for x in trialsToImport]
        [print(x.newId) for x in trialsToImport]



