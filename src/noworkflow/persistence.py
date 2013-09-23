# Copyright (c) 2013 Universidade Federal Fluminense (UFF), Polytechnic Institute of New York University.
# This file is part of noWorkflow. Please, consult the license terms in the LICENSE file.

import os.path
from output import write
import hashlib

PROVENANCE_DIR_NAME = '.noworkflow'
FS_STORE_DIR_NAME = 'db'

provenance_dir = ''
fs_store_dir = ''

def connect(script_dir):
    global provenance_dir, fs_store_dir
    noworkflow_dir = os.path.join(script_dir, PROVENANCE_DIR_NAME)
    if not os.path.isdir(noworkflow_dir):
        write('creating provenance store at {}'.format(noworkflow_dir))
        os.makedirs(noworkflow_dir)
        
    fs_store_dir = os.path.join(provenance_dir, FS_STORE_DIR_NAME)
    if not os.path.isdir(fs_store_dir):
        write('creating file system store at {}'.format(noworkflow_dir))
        os.makedirs(noworkflow_dir)
     
def put(content):
    content_hash = hashlib.sha1(content).hexdigest()
    content_dirname = os.path.join(fs_store_dir, content_hash[:2])
    if (not os.path.isdir(content_dirname)):
        os.mkdir(content_dirname)
    content_filename = os.path.join(content_dirname, content_hash[2:])
    with open(content_filename, "w") as content_file:
        content_file.write(content)
    return content_hash

def get(content_hash):
    content_filename = os.path.join(fs_store_dir, content_hash[:2], content_hash[2:])
    with open(content_filename) as content_file:
        return content_file.read()
        
    