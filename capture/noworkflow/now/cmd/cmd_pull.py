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


from .command import Command


class Pull(Command):
    """Import trials to a database"""
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

    def execute(self, args):

        self.populate(args)
        url=self.url+"/collab/trialsids"

        response = requests.get(url)
        targetUuids=json.loads(response.content)
        
        persistence_config.connect(os.getcwd())

        trialsIds=[t.id for t in Trial.all()]
        trialsToImport=[x for x in targetUuids if x not in trialsIds]

 

        headers = {'Accept-Encoding': 'gzip'}
        url=self.url+"/collab/bundle?id=0&"
        for x in trialsToImport:
            url=url+"&id="+x

        response=requests.get(url, headers=headers)
        content= json.loads(response.content)

        
        bundle=BundleLW()
        bundle.from_json(content)
        
        import_bundle(bundle)

        print("Pulled successfully")

        
       



