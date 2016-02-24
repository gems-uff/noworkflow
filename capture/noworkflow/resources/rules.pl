%
% ID-BASED ACCESSOR RULES FOR
% activation(trial_id, id, name, start, finish, caller_activation_id).
% access(trial_id, id, name, mode, content_hash_before, content_hash_after, timestamp, activation_id).
%

name(_, [], []).
name(Trial_id, [Id|Ids], [Name|Names]) :- name(Trial_id, Id, Name), name(Trial_id, Ids, Names).
name(Trial_id, Id, Name) :- activation(Trial_id, Id, Name, _, _, _).
name(Trial_id, Id, Name) :- access(Trial_id, Id, Name, _, _, _, _, _).

timestamp_id(Trial_id, Id, Start, start) :- activation(Trial_id, Id, _, Start, _, _).
timestamp_id(Trial_id, Id, Finish, finish) :- activation(Trial_id, Id, _, _, Finish, _).
timestamp_id(Trial_id, Id, Timestamp) :- access(Trial_id, Id, _, _, _, _, Timestamp, _).
duration_id(Trial_id, Id, Duration) :- timestamp_id(Trial_id, Id, Start, start), timestamp_id(Trial_id, Id, Finish, finish), Duration is Finish - Start.
successor_id(Trial_id, Before, After) :- timestamp_id(Trial_id, Before, TS1, start), timestamp_id(Trial_id, After, TS2, finish), TS1 =< TS2.
successor_id(Trial_id, Before, After) :- timestamp_id(Trial_id, Before, TS1), timestamp_id(Trial_id, After, TS2), TS1 =< TS2.

activation_id(Trial_id, Caller, Called) :- activation(Trial_id, Called, _, _, _, Caller).

mode_id(Trial_id, Id, Mode) :- access(Trial_id, Id, _, Mode, _, _, _, _).
file_read_id(Trial_id, Id) :- mode_id(Trial_id, Id, Mode), atom_prefix(Mode, 'r').
file_written_id(Trial_id, Id) :- mode_id(Trial_id, Id, Mode), atom_prefix(Mode, 'w').

hash_id(Trial_id, Id, Hash, before) :- access(Trial_id, Id, _, _, Hash, _, _, _).
hash_id(Trial_id, Id, Hash, after) :- access(Trial_id, Id, _, _, _, Hash, _, _).
changed_id(Trial_id, Id) :- hash_id(Trial_id, Id, Hash1, before), hash_id(Trial_id, Id, Hash2, after), Hash1 \== Hash2.

access_id(Trial_id, Function, File) :- access(Trial_id, File, _, _, _, _, _, Function).

%
% ID-BASED INFERENCE RULES
%

activation_stack_id(Trial_id, Called, []) :- activation_id(Trial_id, nil, Called).
activation_stack_id(Trial_id, Called, [Caller|Callers]) :- activation_id(Trial_id, Caller, Called), activation_stack_id(Trial_id, Caller, Callers).

indirect_activation_id(Trial_id, Caller, Called) :- activation_stack_id(Trial_id, Called, Callers), member(Caller, Callers).

% Naive! Should check arguments and return values (program slicing?) to avoid false positives
activation_influence_id(Trial_id, Influencer, Influenced) :- successor_id(Trial_id, Influencer, Influenced).

access_stack_id(Trial_id, File, [Function|Functions]) :- access_id(Trial_id, Function, File), activation_stack_id(Trial_id, Function, Functions).

indirect_access_id(Trial_id, Function, File) :- access_stack_id(Trial_id, File, Functions), member(Function, Functions).

access_influence_id(Trial_id, Influencer, Influenced) :- file_read_id(Trial_id, Influencer), file_written_id(Trial_id, Influenced), successor_id(Trial_id, Influencer, Influenced), access_id(Trial_id, F1, Influencer), access_id(Trial_id, F2, Influenced), activation_influence_id(Trial_id, F1, F2).

%
% NAME-BASED ACCESSOR RULES
%

timestamp(Trial_id, Name, Timestamp, Moment) :- timestamp_id(Trial_id, Id, Timestamp, Moment), name(Trial_id, Id, Name).
timestamp(Trial_id, Name, Timestamp) :- timestamp_id(Trial_id, Id, Timestamp), name(Trial_id, Id, Name).
duration(Trial_id, Name, Duration) :- duration_id(Trial_id, Id, Duration), name(Trial_id, Id, Name).
successor(Trial_id, Before, After) :- successor_id(Trial_id, Before_id, After_id), name(Trial_id, Before_id, Before), name(Trial_id, After_id, After).
mode(Trial_id, Name, Mode) :- mode_id(Trial_id, Id, Mode), name(Trial_id, Id, Name).
file_read(Trial_id, Name) :- file_read_id(Trial_id, Id), name(Trial_id, Id, Name).
file_written(Trial_id, Name) :- file_written_id(Trial_id, Id), name(Trial_id, Id, Name).
hash(Trial_id, Name, Hash, Moment) :- hash_id(Trial_id, Id, Hash, Moment), name(Trial_id, Id, Name).
changed(Trial_id, Name) :- changed_id(Trial_id, Id), name(Trial_id, Id, Name).

%
% NAME-BASED INFERENCE RULES
%

activation_stack(Trial_id, Called, Callers) :- activation_stack_id(Trial_id, Called_id, Caller_ids), name(Trial_id, Called_id, Called), name(Trial_id, Caller_ids, Callers).
indirect_activation(Trial_id, Caller, Called) :- indirect_activation_id(Trial_id, Caller_id, Called_id), name(Trial_id, Called_id, Called), name(Trial_id, Caller_id, Caller).
activation_influence(Trial_id, Influencer, Influenced) :- activation_influence_id(Trial_id, Influencer_id, Influenced_id), name(Trial_id, Influencer_id, Influencer), name(Trial_id, Influenced_id, Influenced).
access_stack(Trial_id, File, Functions) :- access_stack_id(Trial_id, File_id, Functions_id), name(Trial_id, File_id, File), name(Trial_id, Functions_id, Functions).
indirect_access(Trial_id, Function, File) :- indirect_access_id(Trial_id, Function_id, File_id), name(Trial_id, Function_id, Function), name(Trial_id, File_id, File).
access_influence(Trial_id, Influencer, Influenced) :- access_influence_id(Trial_id, Influencer_id, Influenced_id), name(Trial_id, Influencer_id, Influencer), name(Trial_id, Influenced_id, Influenced).

%
% SLICING-BASED ACCESSOR RULES
%

dep(Trial_id, Dependent, Supplier) :- dependency(Trial_id, _, _, Dependent, _, Supplier).
usage_or_assign(Trial_id, Name, Line, Id) :- usage(Trial_id, _, Id, _, Name, Line).
usage_or_assign(Trial_id, Name, Line, Id) :- variable(Trial_id, _, Id, Name, Line, _, _).

var_name(Trial_id, Id, Name) :- variable(Trial_id, _, Id, Name, _, _, _).
var_line(Trial_id, Id, Line) :- variable(Trial_id, _, Id, _, Line, _, _).
var_info(Trial_id, Id, variable(Trial_id, Activation, Id, Name, Line, Value, Timestamp)) :- variable(Trial_id, Activation, Id, Name, Line, Value, Timestamp).


%
% SLICING-BASED INFERENCE RULES
%

slice(_, [],[]).
slice(Trial_id, [Id|L1], L2) :- slice(Trial_id, Id, L3), slice(Trial_id, L1, L4), union(L3, L4, L2), !.
slice(Trial_id, Id, [Id|L1]) :- bagof(X, dep(Trial_id, Id, X),L2), !, slice(Trial_id, L2, L1).
slice(_, Id, [Id]).

variable_name_dependencies(Trial_id, Id, Names) :- slice(Trial_id, Id, X), maplist(var_name(Trial_id), X, Names).
variable_line_dependencies(Trial_id, Id, Lines) :- slice(Trial_id, Id, X), maplist(var_line(Trial_id), X, Lines).
variable_dependencies(Trial_id, Id, Infos) :- slice(Trial_id, Id, X), maplist(var_info(Trial_id), X, Infos).
