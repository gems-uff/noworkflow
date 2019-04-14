# Copyright (c) 2016 Universidade Federal Fluminense (UFF)
# Copyright (c) 2016 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
""""now list" command"""
from __future__ import (absolute_import, print_function,
                        division, unicode_literals)

import os
import shutil


from ..persistence.config import PersistenceConfig
from ..persistence.content_database import ContentDatabase

from .command import Command


class Import(Command):
    """Import trials to a database"""
    def __init__(self, *args, **kwargs):
        super(Import, self).__init__(*args, **kwargs)
        self.targetContent=None
        self.sourceContent=None
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
        targetConfig=PersistenceConfig()  
        self.targetContent=ContentDatabase(targetConfig)  
        targetConfig.connect(args.target or os.getcwd())
        targetFiles=self.targetContent.listAll()
        
        sourceFiles=self.sourceContent.listAll()
        
        toAdd= [x for x in sourceFiles if x not in targetFiles]
        [self.addFile(n) for n in toAdd]
    def addFile(self,name):
        print("Add file: "+name)
        content=self.sourceContent.get(name)
        self.targetContent.put(content)
    def validate(self,args):
        if not (args.source):  
            raise ValueError("--source can't be empty")  
        
        sourceConfig=PersistenceConfig()  
        self.sourceContent=ContentDatabase(sourceConfig)  
        sourceConfig.connect_existing(args.source)
        
    def execute(self, args):

        self.validate(args)
            
        self.import_content(args)
        # Retrieve path to Import