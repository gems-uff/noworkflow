create table trial (
	id INTEGER PRIMARY KEY AUTOINCREMENT,
	start TIMESTAMP,
	finish TIMESTAMP,
	script TEXT,
	code_hash TEXT,
	arguments TEXT,
	inherited_id INTEGER, -- Id of the prospective tuple that we are inheriting module information (due to --bypass-modules)
	parent_id INTEGER, -- Id of the parent trial that is used to create the history
	run INTEGER, -- trial created through now run command
	FOREIGN KEY (inherited_id) REFERENCES trial ON DELETE RESTRICT,
	FOREIGN KEY (parent_id) REFERENCES trial ON DELETE SET NULL
);

CREATE INDEX trial_inherited_id on trial(inherited_id);
CREATE INDEX trial_parent_id on trial(parent_id);

create table head (
	id INTEGER PRIMARY KEY AUTOINCREMENT,
	script TEXT,
	trial_id INTEGER,
	FOREIGN KEY (trial_id) REFERENCES trial ON DELETE SET NULL
);

CREATE INDEX head_trial_id on head(trial_id);

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

CREATE INDEX dependency_trial_id on dependency(trial_id);
CREATE INDEX dependency_module_id on dependency(module_id);

create table function_def (
	id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT,
	code_hash TEXT,
	trial_id INTEGER,
	FOREIGN KEY (trial_id) REFERENCES trial ON DELETE CASCADE
);

CREATE INDEX function_def_trial_id on function_def(trial_id);

create table object (
	id INTEGER PRIMARY KEY AUTOINCREMENT,
	name TEXT,
	type TEXT CHECK (type IN ('GLOBAL', 'ARGUMENT', 'FUNCTION_CALL')),
	function_def_id INTEGER,
	FOREIGN KEY (function_def_id) REFERENCES function_def ON DELETE CASCADE
);

CREATE INDEX object_function_def_id on object(function_def_id);

create table environment_attr (
	id INTEGER PRIMARY KEY AUTOINCREMENT,
	name TEXT,
	value TEXT,
	trial_id INTEGER,
	FOREIGN KEY (trial_id) REFERENCES trial ON DELETE CASCADE
);

CREATE INDEX environment_attr_trial_id on environment_attr(trial_id);

create table function_activation (
	trial_id INTEGER,
	id INTEGER,
	name TEXT,
	line INTEGER,
	return TEXT,
	start TIMESTAMP,
	finish TIMESTAMP,
	caller_id INTEGER,
	FOREIGN KEY (caller_id) REFERENCES function_activation ON DELETE CASCADE,
	FOREIGN KEY (trial_id) REFERENCES trial ON DELETE CASCADE,
	PRIMARY KEY (trial_id, id)
);

CREATE INDEX function_activation_caller_id on function_activation(caller_id);
CREATE INDEX function_activation_trial_id on function_activation(trial_id);

create table object_value (
	trial_id INTEGER,
	function_activation_id INTEGER,
	id INTEGER,
	name TEXT,
	value TEXT,
	type TEXT CHECK (type IN ('GLOBAL', 'ARGUMENT')),
	FOREIGN KEY (function_activation_id) REFERENCES function_activation ON DELETE CASCADE,
	PRIMARY KEY (trial_id, function_activation_id, id)
);

CREATE INDEX object_value_function_activation_id on object_value(function_activation_id);

create table file_access (
	trial_id INTEGER,
	id INTEGER,
	name TEXT,
	mode TEXT,
	buffering TEXT,
	content_hash_before TEXT,
	content_hash_after TEXT,
	timestamp TIMESTAMP,
	function_activation_id INTEGER,
	FOREIGN KEY (function_activation_id) REFERENCES function_activation ON DELETE CASCADE,
	FOREIGN KEY (trial_id) REFERENCES trial ON DELETE CASCADE,
	PRIMARY KEY (trial_id, id)
);

CREATE INDEX file_access_function_activation_id on file_access(function_activation_id);
CREATE INDEX file_access_trial_id on file_access(trial_id);

-- Slicing

create table slicing_variable (
	trial_id INTEGER,
	vid INTEGER,
    name TEXT,
	line INTEGER,
	value TEXT,
	time TIMESTAMP,
	FOREIGN KEY (trial_id) REFERENCES trial ON DELETE CASCADE,
	PRIMARY KEY (trial_id, vid)
);

CREATE INDEX slicing_variable_trial_id on slicing_variable(trial_id);
CREATE INDEX slicing_variable_vid on slicing_variable(vid);

create table slicing_usage (
	trial_id INTEGER,
	id INTEGER,
	vid INTEGER,
    name TEXT,
	line INTEGER,
	context TEXT CHECK (context IN ('Load', 'Del')),
	FOREIGN KEY (trial_id, vid) REFERENCES slicing_variable(trial_id, vid) ON DELETE CASCADE,
	PRIMARY KEY (trial_id, id)
);

CREATE INDEX slicing_usage_trial_id on slicing_usage(trial_id);
CREATE INDEX slicing_usage_vid on slicing_usage(vid);

create table slicing_dependency (
	trial_id INTEGER,
	id INTEGER,
	dependent INTEGER,
	supplier INTEGER,
	FOREIGN KEY (trial_id, dependent) REFERENCES slicing_variable(trial_id, vid) ON DELETE CASCADE,
	FOREIGN KEY (trial_id, supplier) REFERENCES slicing_variable(trial_id, vid) ON DELETE CASCADE,
	PRIMARY KEY (trial_id, id)
);

CREATE INDEX slicing_dependency_trial_id on slicing_dependency(trial_id);
CREATE INDEX slicing_dependency_dependent on slicing_dependency(dependent);
CREATE INDEX slicing_dependency_supplier on slicing_dependency(supplier);

-- Cache

create table graph_cache (
	id INTEGER PRIMARY KEY AUTOINCREMENT,
	type TEXT,
	name TEXT,
	attributes TEXT,
	content_hash TEXT,
	duration INTEGER,
	timestamp TIMESTAMP
);

