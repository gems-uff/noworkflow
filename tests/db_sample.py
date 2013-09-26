import os
import sqlite3

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
    conn.execute("""
    insert into test (id, data) 
    values (1, 'row 1') 
    """)    
    conn.commit()
else:
    print 'Database exists, assuming schema does, too.'
    cursor = conn.cursor()
    cursor.execute("""
    select id, data from test
    """)
        
    for row in cursor.fetchall():
        table_id, data = row
        print '%2d %s' % (table_id, data)

conn.close()