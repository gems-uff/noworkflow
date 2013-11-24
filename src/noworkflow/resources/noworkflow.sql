create table trial (
	id INTEGER PRIMARY KEY AUTOINCREMENT,
	start TIMESTAMP,
	finish TIMESTAMP,
	script TEXT,
	code_hash TEXT,
	inherited_id INTEGER, -- Id of the prospective tuple that we are inheriting module information (due to --bypass-modules)
	FOREIGN KEY (inherited_id) REFERENCES trial ON DELETE RESTRICT  
);

create table module (
	id INTEGER PRIMARY KEY AUTOINCREMENT,
	name TEXT,
	version TEXT,
	file TEXT,
	code_hash TEXT,
	trial_id INTEGER,
	FOREIGN KEY (trial_id) REFERENCES trial ON DELETE CASCADE
);

create table function_def (
	id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT,
	code_hash TEXT,
	trial_id INTEGER,
	FOREIGN KEY (trial_id) REFERENCES trial ON DELETE CASCADE
);

create table object (
	id INTEGER PRIMARY KEY AUTOINCREMENT,
	name TEXT,
	type TEXT CHECK (type IN ('GLOBAL', 'ARGUMENT', 'FUNCTION')),
	function_def_id INTEGER,
	FOREIGN KEY (function_def_id) REFERENCES function_def ON DELETE CASCADE
);

create table environment_attr (
	id INTEGER PRIMARY KEY AUTOINCREMENT,
	name TEXT,
	value TEXT,
	trial_id INTEGER,
	FOREIGN KEY (trial_id) REFERENCES trial ON DELETE CASCADE
);

create table function_call (
	id INTEGER PRIMARY KEY AUTOINCREMENT,
	name TEXT,
	line INTEGER,
	return TEXT,
	start TIMESTAMP,
	finish TIMESTAMP,
	caller_id INTEGER,
	trial_id INTEGER,
	FOREIGN KEY (caller_id) REFERENCES function_call ON DELETE CASCADE,
	FOREIGN KEY (trial_id) REFERENCES trial ON DELETE CASCADE	
);

create table object_value (
	id INTEGER PRIMARY KEY AUTOINCREMENT,
	name TEXT,
	value TEXT,
	type TEXT CHECK (type IN ('GLOBAL', 'ARGUMENT')),
	function_call_id INTEGER,
	FOREIGN KEY (function_call_id) REFERENCES function_call ON DELETE CASCADE
);

create table file_access (
	id INTEGER PRIMARY KEY AUTOINCREMENT,
	name TEXT,
	mode TEXT,
	buffering TEXT,
	content_hash_before TEXT,
	content_hash_after TEXT,
	timestamp TIMESTAMP,
	function_call_id INTEGER,
	trial_id INTEGER,
	FOREIGN KEY (function_call_id) REFERENCES function_call ON DELETE CASCADE,
	FOREIGN KEY (trial_id) REFERENCES trial ON DELETE CASCADE
);