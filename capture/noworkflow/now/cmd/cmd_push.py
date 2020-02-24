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
from ..utils.compression import gzip_compress

from ..persistence.models import Trial
from ..persistence import content

from .command import Command
from zipfile import ZipFile
from io import BytesIO

class Push(Command):
    """Import trials to a database"""
    def __init__(self, *args, **kwargs):
        super(Push, self).__init__(*args, **kwargs)
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

    def exportTrials(self):
        url=self.url+"/collab/trialsids"
        targetUuids=self.get(url)

        trials=[t for t in Trial.all()]
        trialsToExport=[x.id for x in trials if x.id not in targetUuids]

        bundle=export_bundle(trialsToExport)

        headers = {'Content-Encoding': 'gzip'}
        url=self.url+"/collab/bundle"
        
        ziped_data=gzip_compress(json.dumps(bundle.__json__()).encode())
        response=requests.post(url, data= ziped_data, headers=headers)
        return response.status_code
    def exportFile(self,fileName,url):
        print("Sending file: "+fileName)
        headers = {'Content-Encoding': 'gzip'}
        ziped_data=gzip_compress(content.get(fileName))
        response=requests.post(url, data= ziped_data, headers=headers)
        if(response.status_code!=201):
            print("Error sending file: "+fileName)
    def exportFiles(self):
        filesUrl=self.url+"/collab/files"
        targetFiles=self.get(filesUrl)
        sourceFiles=content.listAll()
        filesToExport=[x for x in sourceFiles if x not in targetFiles]
        if (filesToExport.__len__()>0):
            zipF=BytesIO()
            zipObj = ZipFile(zipF, 'w')
            for fileName in filesToExport:
                zipObj.writestr(fileName,content.get(fileName))
            
            zipObj.close()
            zipF.seek(0)
            multipart_form_data = {
                'files': ('files.zip', zipF,'application/zip')
            }
            
            response = requests.post(filesUrl, files=multipart_form_data)

            zipF.close()

    def execute(self, args):

        self.populate(args)

        persistence_config.connect(os.getcwd())
        print("Exporting Files...")
        self.exportFiles()
        print("Exporting Trials...")
        status_code=self.exportTrials()
        

        if(status_code==201):
            print("Pushed successfully")
        else:
            print("Error pushing")

        
       



