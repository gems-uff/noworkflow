# Copyright (c) 2013 Universidade Federal Fluminense (UFF), Polytechnic Institute of New York University.
# This file is part of noWorkflow. Please, consult the license terms in the LICENSE file.

import os.path
import hashlib
import sqlite3
from utils import print_msg
from pkg_resources import resource_string  #@UnresolvedImport

PROVENANCE_DIRNAME = '.noworkflow'
CONTENT_DIRNAME = 'content'
DB_FILENAME = 'db.sqlite'
DB_SCRIPT = 'noworkflow.sql'

content_path = None  # Base path for storing content of files
db_conn = None  # Connection to the database
prospective_id = None  # Id of the prospective provenance used in this trial

std_open = open  # Original Python open function.

def connect(script_dir):
    global content_path, db_conn
    provenance_path = os.path.join(script_dir, PROVENANCE_DIRNAME)
            
    content_path = os.path.join(provenance_path, CONTENT_DIRNAME)
    if not os.path.isdir(content_path):
        os.makedirs(content_path)

    db_path = os.path.join(provenance_path, DB_FILENAME)
    new_db = not os.path.exists(db_path)
    db_conn = sqlite3.connect(db_path)
    if new_db:
        print_msg('creating provenance database')
        with db_conn as db:
            db.executescript(resource_string(__name__, DB_SCRIPT))  # Accessing the content of a file via setuptools
            
      
# FILE ACCESS FUNCTIONS

def register_file_access(name, mode = 'r', buffering = 'default'):
    'registers an access to a file'
    with std_open(name, 'rb') as f:
        content_hash = put(f.read())
        # TODO: store the content hash together with access type in the current context and its call stack
        
        
# CONTENT STORAGE FUNCTIONS
            
def put(content):
    content_hash = hashlib.sha1(content).hexdigest()
    content_dirname = os.path.join(content_path, content_hash[:2])
    if not os.path.isdir(content_dirname):
        os.makedirs(content_dirname)
    content_filename = os.path.join(content_dirname, content_hash[2:])
    if not os.path.isfile(content_filename):
        with std_open(content_filename, "wb") as content_file:
            content_file.write(content)
    return content_hash


def get(content_hash):
    content_filename = os.path.join(content_path, content_hash[:2], content_hash[2:])
    with std_open(content_filename, 'rb') as content_file:
        return content_file.read()


# DATABASE STORE/RETRIEVE FUNCTIONS
# TODO: Avoid replicating information in the DB. This will also help when diffing data.

def store_prospective(tstamp, bypass_modules):
    global prospective_id
    with db_conn as db:
        if bypass_modules:
            (iherited_id,) = db.execute("select id from prospective where tstamp in (select max(tstamp) from prospective where inherited_id is NULL)").fetchone()
        else:
            iherited_id = None
        
        prospective_id = db.execute("insert into prospective (tstamp, inherited_id) values (?, ?)", (tstamp, iherited_id)).lastrowid
        

def store_environment(env_attrs):
    data = [(name, value, prospective_id) for name, value in env_attrs.iteritems()]
    with db_conn as db:
        db.executemany("insert into environment_attribute(name, value, prospective_id) values (?, ?, ?)", data)
        

def store_dependencies(dependencies):
    data = [(name, version, path, code_hash, prospective_id) for name, version, path, code_hash in dependencies]    
    with db_conn as db:
        db.executemany("insert into module(name, version, file, code_hash, prospective_id) values (?, ?, ?, ?, ?)", data)


def retrieve_iherited_id(an_id):
    with db_conn as db:
        (iherited_id,) = db.execute("select inherited_id from prospective where id = ?", (an_id,)).fetchone()
    return iherited_id

        
def retrieve_dependencies():
    an_id = retrieve_iherited_id(prospective_id)
    if not an_id: an_id = prospective_id
    with db_conn as db:
        return db.execute("select name, version, file, code_hash from module where prospective_id = ?", (an_id,)).fetchall()


def store_objects(objects, obj_type, function_def_id):
    data = [(name, obj_type, function_def_id) for name in objects]
    with db_conn as db:
        db.executemany("insert into object(name, type, function_def_id) values (?, ?, ?)", data)    


def store_function_defs(functions):  
    with db_conn as db:
        for name, (arguments, global_vars, calls, code_hash) in functions.items():
            function_def_id = db.execute("insert into function_def(name, code_hash, prospective_id) values (?, ?, ?)", (name, code_hash, prospective_id)).lastrowid
            store_objects(arguments, 'ARGUMENT', function_def_id)
            store_objects(global_vars, 'GLOBAL', function_def_id)
            store_objects(calls, 'FUNCTION', function_def_id)