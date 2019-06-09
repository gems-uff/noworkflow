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


from .command import Command


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

    def execute(self, args):

        self.populate(args)
        url=self.url+"/collab/trialsids"
        response = requests.get(url)
        targetUuids=json.loads(response.content)
        
        persistence_config.connect(os.getcwd())

        trials=[t for t in Trial.all()]
        trialsToExport=[x.id for x in trials if x.id not in targetUuids]

        bundle=export_bundle(trialsToExport)

        headers = {'Content-Encoding': 'gzip'}
        url=self.url+"/collab/bundle"
        

        ziped_data=gzip_compress(json.dumps(bundle.__json__()).encode())
        

        response=requests.post(url, data= ziped_data, headers=headers)

        if(response.status_code==201):
            print("Pushed successfully")
        else:
            print("Error pushing")

        
       



