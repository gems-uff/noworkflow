create table prospective_provenance (
	id INTEGER PRIMARY KEY AUTOINCREMENT,
	tstamp TIMESTAMP
);

create table module (
	id INTEGER PRIMARY KEY AUTOINCREMENT,
	name TEXT,
	version TEXT,
	file TEXT,
	code_hash TEXT,
	prospective_provenance_id INTEGER,
	FOREIGN KEY (prospective_provenance_id) REFERENCES prospective_provenance ON DELETE CASCADE
);

create table environment_attribute (
	id INTEGER PRIMARY KEY AUTOINCREMENT,
	name TEXT,
	value TEXT,
	prospective_provenance_id INTEGER,
	FOREIGN KEY (prospective_provenance_id) REFERENCES prospective_provenance ON DELETE CASCADE
);

create table function_def (
	id INTEGER PRIMARY KEY AUTOINCREMENT,
	code_hash TEXT,
	prospective_provenance_id INTEGER,
	depends_on INTEGER,
	FOREIGN KEY (prospective_provenance_id) REFERENCES prospective_provenance ON DELETE CASCADE,
	FOREIGN KEY (depends_on) REFERENCES function_def ON DELETE CASCADE
);

create table function_def_arguments (
	id INTEGER PRIMARY KEY AUTOINCREMENT,
	name TEXT,
	function_def_id INTEGER,
	FOREIGN KEY (function_def_id) REFERENCES function_def ON DELETE CASCADE
);

create table retrospective_provenance (
	id INTEGER PRIMARY KEY AUTOINCREMENT,
	tstamp TIMESTAMP,
	user TEXT,
	prospective_provenance_id INTEGER,
	FOREIGN KEY (prospective_provenance_id) REFERENCES prospective_provenance ON DELETE CASCADE
);

create table function (
	id INTEGER PRIMARY KEY AUTOINCREMENT,
	script_name TEXT,
	function_name TEXT,
	line_numebr INTEGER,
	start TIMESTAMP,
	finish TIMESTAMP,
	retrospective_provenance_id INTEGER,
	called_by INTEGER,
	FOREIGN KEY (retrospective_provenance_id) REFERENCES retrospective_provenance ON DELETE CASCADE
	FOREIGN KEY (called_by) REFERENCES function ON DELETE CASCADE
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