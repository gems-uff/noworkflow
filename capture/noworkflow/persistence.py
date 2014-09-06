# Copyright (c) 2013 Universidade Federal Fluminense (UFF), Polytechnic Institute of New York University.
# This file is part of noWorkflow. Please, consult the license terms in the LICENSE file.

import hashlib
import os.path
import sqlite3
import sys
from collections import deque
from pkg_resources import resource_string #@UnresolvedImport

from utils import print_msg


PROVENANCE_DIRNAME = '.noworkflow'
CONTENT_DIRNAME = 'content'
DB_FILENAME = 'db.sqlite'
DB_SCRIPT = 'resources/noworkflow.sql'

content_path = None  # Base path for storing content of files
db_conn = None  # Connection to the database
trial_id = None  # Id of the prospective provenance used in this trial

std_open = open  # Original Python open function.


def has_provenance(path):
    provenance_path = os.path.join(path, PROVENANCE_DIRNAME)
    return os.path.isdir(provenance_path)


def connect(path):
    global content_path, db_conn
    provenance_path = os.path.join(path, PROVENANCE_DIRNAME)

    content_path = os.path.join(provenance_path, CONTENT_DIRNAME)
    if not os.path.isdir(content_path):
        os.makedirs(content_path)

    db_path = os.path.join(provenance_path, DB_FILENAME)
    new_db = not os.path.exists(db_path)
    db_conn = sqlite3.connect(db_path)
    db_conn.row_factory = sqlite3.Row
    if new_db:
        print_msg('creating provenance database')
        # Accessing the content of a file via setuptools
        with db_conn as db:
            db.executescript(resource_string(__name__, DB_SCRIPT))


def connect_existing(path):
    if not has_provenance(path):
        print_msg('there is no provenance store in the current directory',
                  True)
        sys.exit(1)
    connect(path)


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
    content_filename = os.path.join(content_path, content_hash[:2],
                                    content_hash[2:])
    with std_open(content_filename, 'rb') as content_file:
        return content_file.read()


# DATABASE STORE/RETRIEVE FUNCTIONS

def load(table_name, selection=["*"], **condition):
    where = '1'
    for key in condition:
        if condition[key] is None:
            where += ' and {} is NULL'.format(key)
        else:
            where += ' and {} = {}'.format(key, condition[key])

    with db_conn as db:
        return db.execute('select {} from {} where {} order by id'.format(
            ','.join(selection), table_name, where))


def insert(table_name, attrs, **extra_attrs):
    # Not in use, but can be useful in the future
    query = 'insert into {}({}) values ({})'.format(
        table_name,
        ','.join(attrs.keys() + extra_attrs.keys()),
        ','.join(['?'] * (len(attrs) + len(extra_attrs)))
    )
    with db_conn as db:
        db.execute(query, attrs.values() + extra_attrs.values())


def insertmany(table_name, attrs_list, **extra_attrs):
    # Not in use, but can be useful in the future
    for attrs in attrs_list:
        insert(table_name, attrs, **extra_attrs)


def last_trial_id():
    with db_conn as db:
        (an_id,) = db.execute("select id from trial where start in (select max(start) from trial)").fetchone()
    return an_id


def last_trial_id_without_iheritance():
    with db_conn as db:
        (an_id,) = db.execute("select id from trial where start in (select max(start) from trial where inherited_id is NULL)").fetchone()
    return an_id


def function_activation_id_seq():
    try:
        with db_conn as db:
            (an_id,) = db.execute("select seq from SQLITE_SEQUENCE WHERE name='function_activation'").fetchone()
    except TypeError:
        an_id = 0
    return an_id + 1


def iherited_id(an_id):
    with db_conn as db:
        (iherited_id,) = db.execute("select inherited_id from trial where id = ?", (an_id,)).fetchone()
    return iherited_id


def store_trial(start, script, code, arguments, bypass_modules):
    global trial_id
    code_hash = put(code.encode('utf-8'))
    iherited_id = last_trial_id_without_iheritance() if bypass_modules else None
    with db_conn as db:
        trial_id = db.execute("insert into trial (start, script, code_hash, arguments, inherited_id) values (?, ?, ?, ?, ?)", (start, script, code_hash, arguments, iherited_id)).lastrowid


def update_trial(finish, function_activation):
    store_function_activation(function_activation, None)
    with db_conn as db:
        db.execute("update trial set finish = ? where id = ?", (finish, trial_id))


def load_trial(an_id):
    global trial_id
    trial_id = an_id
    return load('trial', id=trial_id)


def store_dependencies(dependencies):
    with db_conn as db:
        for (name, version, path, code_hash) in dependencies:
            modules = db.execute('select id from module where name = ? and (version is null or version = ?) and (code_hash is null or code_hash = ?)', (name, version, code_hash)).fetchone()
            if modules:
                (module_id,) = modules
            else:
                module_id = db.execute("insert into module (name, version, path, code_hash) values (?, ?, ?, ?)", (name, version, path, code_hash)).lastrowid
            db.execute("insert into dependency (trial_id, module_id) values (?, ?)", (trial_id, module_id))


def load_dependencies():
    an_id = iherited_id(trial_id)
    if not an_id:
        an_id = trial_id
    with db_conn as db:
        return db.execute('select id, name, version, path, code_hash from module as m, dependency as d where m.id = d.module_id and d.trial_id = ? order by id', (an_id,))


def store_environment(env_attrs):
    with db_conn as db:
        db.executemany(
            "insert into environment_attr(name, value, trial_id) values (?, ?, ?)", 
            ((name, env_attrs[name], trial_id) for name in env_attrs)
        )


def store_objects(objects, obj_type, function_def_id):
    with db_conn as db:
        db.executemany(
            "insert into object(name, type, function_def_id) values (?, ?, ?)",
            ((name, obj_type, function_def_id) for name in objects)
        )


def store_function_defs(functions):
    with db_conn as db:
        for name, (arguments, global_vars, calls, code_hash) in functions.items():
            function_def_id = db.execute("insert into function_def(name, code_hash, trial_id) values (?, ?, ?)", (name, code_hash, trial_id)).lastrowid
            store_objects(arguments, 'ARGUMENT', function_def_id)
            store_objects(global_vars, 'GLOBAL', function_def_id)
            store_objects(calls, 'FUNCTION_CALL', function_def_id)


def extract_function_activation(function_activation, caller_id, function_activation_id):
    return (
        function_activation_id,
        function_activation['name'],
        function_activation['line'],
        function_activation['return'],
        function_activation['start'],
        function_activation['finish'],
        caller_id,
        trial_id,
    )


def extract_object_values(object_values, obj_type, function_activation_id):
    for name in object_values:
        yield (name, object_values[name], obj_type, function_activation_id)


def extract_file_accesses(file_accesses, function_activation_id):
    for file_access in file_accesses:
        yield (
            file_access['name'],
            file_access['mode'],
            file_access['buffering'],
            file_access['content_hash_before'],
            file_access['content_hash_after'],
            file_access['timestamp'],
            function_activation_id,
            trial_id
        )


def store_function_activation(function_activation, caller_id):
    function_activations, object_values, file_accesses = [], [], []
    d = { 
        'fid': function_activation_id_seq(),
        'activations': function_activations,
        'object_values': object_values,
        'file_accesses': file_accesses,
    }

    def add_activation(function_activation, caller_id):
        fid = d['fid']
        d['activations'].append(
            extract_function_activation(function_activation, caller_id, fid)
        )
        for object_value in extract_object_values(function_activation['arguments'], 'ARGUMENT', fid):
            d['object_values'].append(object_value)

        for object_value in extract_object_values(function_activation['globals'], 'GLOBAL', fid):
            d['object_values'].append(object_value)

        for file_access in extract_file_accesses(function_activation['file_accesses'], fid):
            d['file_accesses'].append(file_access)

        d['fid'] += 1
        
        for inner_function_activation in function_activation['function_activations']:
            add_activation(inner_function_activation, fid)

    add_activation(function_activation, caller_id)


    with db_conn as db:
        db.executemany(
            "insert into function_activation(id, name, line, return, start, finish, caller_id, trial_id) values (?, ?, ?, ?, ?, ?, ?, ?)",
            function_activations
        )
        db.executemany(
            "insert into object_value(name, value, type, function_activation_id) values (?, ?, ?, ?)",
            object_values
        )
        db.executemany(
            "insert into file_access(name, mode, buffering, content_hash_before, content_hash_after, timestamp, function_activation_id, trial_id) values (?, ?, ?, ?, ?, ?, ?, ?)",
            file_accesses
        )
