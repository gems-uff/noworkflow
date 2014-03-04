create table trial (
	id INTEGER PRIMARY KEY AUTOINCREMENT,
	start TIMESTAMP,
	finish TIMESTAMP,
	script TEXT,
	code_hash TEXT,
	arguments TEXT,
	inherited_id INTEGER, -- Id of the prospective tuple that we are inheriting module information (due to --bypass-modules)
	FOREIGN KEY (inherited_id) REFERENCES trial ON DELETE RESTRICT  
);

create table module (
	id INTEGER PRIMARY KEY AUTOINCREMENT,
	name TEXT,
	version TEXT,
	path TEXT,
	code_hash TEXT
);

create table dependency (
    trial_id INTEGER NOT NULL,
    module_id INTEGER NOT NULL,
    PRIMARY KEY (trial_id, module_id),
	FOREIGN KEY (trial_id) REFERENCES trial ON DELETE CASCADE,
	FOREIGN KEY (module_id) REFERENCES module ON DELETE CASCADE    
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

create table function_activation (
	id INTEGER PRIMARY KEY AUTOINCREMENT,
	name TEXT,
	line INTEGER,
	return TEXT,
	start TIMESTAMP,
	finish TIMESTAMP,
	caller_id INTEGER,
	trial_id INTEGER,
	FOREIGN KEY (caller_id) REFERENCES function_activation ON DELETE CASCADE,
	FOREIGN KEY (trial_id) REFERENCES trial ON DELETE CASCADE	
);

create table object_value (
	id INTEGER PRIMARY KEY AUTOINCREMENT,
	name TEXT,
	value TEXT,
	type TEXT CHECK (type IN ('GLOBAL', 'ARGUMENT')),
	function_activation_id INTEGER,
	FOREIGN KEY (function_activation_id) REFERENCES function_activation ON DELETE CASCADE
);

create table file_access (
	id INTEGER PRIMARY KEY AUTOINCREMENT,
	name TEXT,
	mode TEXT,
	buffering TEXT,
	content_hash_before TEXT,
	content_hash_after TEXT,
	timestamp TIMESTAMP,
	function_activation_id INTEGER,
	trial_id INTEGER,
	FOREIGN KEY (function_activation_id) REFERENCES function_activation ON DELETE CASCADE,
	FOREIGN KEY (trial_id) REFERENCES trial ON DELETE CASCADE
);