import os
import sqlite3
import datetime

#see tutorial at http://pymotw.com/2/sqlite3/

db_filename = 'noworkflow.db'
db_script = 'noworkflow.sql'

db_is_new = not os.path.exists(db_filename)
conn = sqlite3.connect(db_filename)

if db_is_new:
    print 'Creating database schema...'
    with open(db_script, 'rt') as f:
        schema = f.read()
        conn.executescript(schema)

    print 'Inserting sample data...'
    now = datetime.datetime.now()
    print now
    conn.execute("insert into prospective_provenance (tstamp) values (?)", (now,))
    
    # se tstamp eh TEXT, tem que usar funcao de conversao  --> FUNCIONA OK
    # conn.execute("insert into prospective_provenance (tstamp) values (strftime('%Y-%m-%d %H:%M:%S',?))", (now,))
    
    conn.commit()
else:
    print 'Database exists, assuming schema does, too.'
    cursor = conn.cursor()
    cursor.execute("""
    select id, tstamp from prospective_provenance
    """)

    for row in cursor.fetchall():
        table_id, timestamp = row
        print '%2d %s' % (table_id, timestamp)

conn.close()
