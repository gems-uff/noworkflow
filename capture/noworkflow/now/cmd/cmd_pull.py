# Copyright (c) 2016 Universidade Federal Fluminense (UFF)
# Copyright (c) 2016 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
""""now push" command"""

import requests
import os
import json
from ..persistence import persistence_config
from ..utils.collab import export_bundle,import_bundle
from ..utils.compression import gzip_uncompress
from ..persistence.lightweight import BundleLW
from ..persistence.models import Trial
from ..persistence import content

from .command import Command


class Pull(Command):
    """Fetches and downloads a remote provenance database and merges their data with your local provenance database"""
    
    text_invalid_experiment_id = "Invalid experiment ID"
    text_importing_files_failed = "Importing files failed."
    text_importing_trials_failed = "Importing trials failed."
    
    def __init__(self, *args, **kwargs):
        super(Pull, self).__init__(*args, **kwargs)
        self.url=None
  

    def add_arguments(self):
        add_arg = self.add_argument
        add_arg("--url", type=str,
                help="set target url of push command")

    def populate(self,args):
        if not (args.url):  
            raise ValueError("--url can't be empty")
        self.url=args.url

    def get(self,url):
        headers = {'Accept-Encoding': 'gzip'}
        response=requests.get(url, headers=headers)
        return json.loads(response.content)

    def importTrials(self,url):
        trialUrls=self.url+"/collab/trialsids"
        targetUuids=self.get(trialUrls)
        
        if targetUuids == self.text_invalid_experiment_id:
            print(self.text_importing_trials_failed + " " + targetUuids)
            return False
        
        trialsIds=[t.id for t in Trial.all()]
        trialsToImport=[x for x in targetUuids if x not in trialsIds]
        bundleUrls=self.url+"/collab/bundle?id=0&"
        for x in trialsToImport:
            bundleUrls=bundleUrls+"&id="+x

        pvContent=self.get(bundleUrls)
        
        bundle=BundleLW()
        bundle.from_json(pvContent)
        
        import_bundle(bundle)
        
        return True
    
    def importFile(self,url):
        print("Importing file: "+url)
        headers = {'Accept-Encoding': 'gzip'}
        response=requests.get(url, headers=headers)
        content.put(response.content, None)

    def importFiles(self,url):
        filesUrl=self.url+"/collab/files"
        sourceFiles=self.get(filesUrl)
        if sourceFiles == self.text_invalid_experiment_id:
            print(self.text_importing_files_failed + " " + sourceFiles)
            return False
        targetFiles=content.listAll()
        filesToImport=[x for x in sourceFiles if x not in targetFiles]
        [self.importFile(filesUrl+"/"+x) for x in filesToImport]
        
        return True

    def execute(self, args):

        self.populate(args)
        
        persistence_config.connect(os.getcwd())

        importFilesSuccess = self.importFiles(self.url)
        print("Importing trials")
        importTrialsSuccess = self.importTrials(self.url)
        
        if importFilesSuccess and importTrialsSuccess: print("Pulled successfully")

        
       



