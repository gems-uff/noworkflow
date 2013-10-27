create table prospective (
	id INTEGER PRIMARY KEY AUTOINCREMENT,
	tstamp TIMESTAMP,
	inherited_id INTEGER, -- Id of the prospective tuple that we are inheriting module information (due to --bypass-modules)
	FOREIGN KEY (inherited_id) REFERENCES prospective ON DELETE RESTRICT  
);

create table module (
	id INTEGER PRIMARY KEY AUTOINCREMENT,
	name TEXT,
	version TEXT,
	file TEXT,
	code_hash TEXT,
	prospective_id INTEGER,
	FOREIGN KEY (prospective_id) REFERENCES prospective ON DELETE CASCADE
);

create table environment_attribute (
	id INTEGER PRIMARY KEY AUTOINCREMENT,
	name TEXT,
	value TEXT,
	prospective_id INTEGER,
	FOREIGN KEY (prospective_id) REFERENCES prospective ON DELETE CASCADE
);

create table function_def (
	id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT,
	code_hash TEXT,
	prospective_id INTEGER,
	FOREIGN KEY (prospective_id) REFERENCES prospective ON DELETE CASCADE
);

create table object (
	id INTEGER PRIMARY KEY AUTOINCREMENT,
	name TEXT,
	type TEXT CHECK (type IN ('GLOBAL', 'ARGUMENT', 'FUNCTION')),
	function_def_id INTEGER,
	FOREIGN KEY (function_def_id) REFERENCES function_def ON DELETE CASCADE
);

create table retrospective (
	id INTEGER PRIMARY KEY AUTOINCREMENT,
	tstamp TIMESTAMP,
	user TEXT,
	prospective_id INTEGER,
	FOREIGN KEY (prospective_id) REFERENCES prospective ON DELETE CASCADE
);

create table function (
	id INTEGER PRIMARY KEY AUTOINCREMENT,
	script_name TEXT,
	function_name TEXT,
	line_numebr INTEGER,
	start TIMESTAMP,
	finish TIMESTAMP,
	retrospective_id INTEGER,
	FOREIGN KEY (retrospective_id) REFERENCES retrospective ON DELETE CASCADE
);

create table function_call (
	callee_id INTEGER NOT NULL,
	called_id INTEGER NOT NULL,
	PRIMARY KEY (callee_id, called_id),
	FOREIGN KEY (callee_id) REFERENCES function ON DELETE CASCADE,
	FOREIGN KEY (called_id) REFERENCES function ON DELETE CASCADE
);

create table file (
	id INTEGER PRIMARY KEY AUTOINCREMENT,
	name TEXT,
	mode TEXT,
	content_hash_before TEXT,
	content_hash_after TEXT,
	tstamp TIMESTAMP,
	function_id INTEGER,
	FOREIGN KEY (function_id) REFERENCES function ON DELETE CASCADE
);