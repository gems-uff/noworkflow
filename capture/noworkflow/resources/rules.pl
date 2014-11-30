%
% ID-BASED ACCESSOR RULES FOR
% activation(id, name, start, finish, caller_activation_id).
% access(id, name, mode, content_hash_before, content_hash_after, timestamp, activation_id).
%

name([], []).
name([Id|Ids], [Name|Names]) :- name(Id, Name), name(Ids, Names).
name(Id, Name) :- activation(Id, Name, _, _, _).
name(Id, Name) :- access(Id, Name, _, _, _, _, _).

timestamp_id(Id, Start, start) :- activation(Id, _, Start, _, _).
timestamp_id(Id, Finish, finish) :- activation(Id, _, _, Finish, _).
timestamp_id(Id, Timestamp) :- access(Id, _, _, _, _, Timestamp, _).
duration_id(Id, Duration) :- timestamp_id(Id, Start, start), timestamp_id(Id, Finish, finish), Duration is Finish - Start.
successor_id(Before, After) :- timestamp_id(Before, TS1, start), timestamp_id(After, TS2, finish), TS1 =< TS2.
successor_id(Before, After) :- timestamp_id(Before, TS1), timestamp_id(After, TS2), TS1 =< TS2.

activation_id(Caller, Called) :- activation(Called, _, _, _, Caller).

mode_id(Id, Mode) :- access(Id, _, Mode, _, _, _, _).
file_read_id(Id) :- mode_id(Id, Mode), atom_prefix(Mode, 'r').
file_written_id(Id) :- mode_id(Id, Mode), atom_prefix(Mode, 'w').

hash_id(Id, Hash, before) :- access(Id, _, _, Hash, _, _, _).
hash_id(Id, Hash, after) :- access(Id, _, _, _, Hash, _, _).
changed_id(Id) :- hash_id(Id, Hash1, before), hash_id(Id, Hash2, after), Hash1 \== Hash2.

access_id(Function, File) :- access(File, _, _, _, _, _, Function).

%
% ID-BASED INFERENCE RULES
%

activation_stack_id(Called, []) :- activation_id(nil, Called).
activation_stack_id(Called, [Caller|Callers]) :- activation_id(Caller, Called), activation_stack_id(Caller, Callers).

indirect_activation_id(Caller, Called) :- activation_stack_id(Called, Callers), member(Caller, Callers).

% Naive! Should check arguments and return values (program slicing?) to avoid false positives
activation_influence_id(Influencer, Influenced) :- successor_id(Influencer, Influenced).

access_stack_id(File, [Function|Functions]) :- access_id(Function, File), activation_stack_id(Function, Functions).

indirect_access_id(Function, File) :- access_stack_id(File, Functions), member(Function, Functions).

access_influence_id(Influencer, Influenced) :- file_read_id(Influencer), file_written_id(Influenced), successor_id(Influencer, Influenced), access_id(F1, Influencer), access_id(F2, Influenced), activation_influence_id(F1, F2).

%
% NAME-BASED ACCESSOR RULES
%

timestamp(Name, Timestamp, Moment) :- timestamp_id(Id, Timestamp, Moment), name(Id, Name).
timestamp(Name, Timestamp) :- timestamp_id(Id, Timestamp), name(Id, Name).
duration(Name, Duration) :- duration_id(Id, Duration), name(Id, Name).
successor(Before, After) :- successor_id(Before_id, After_id), name(Before_id, Before), name(After_id, After).
mode(Name, Mode) :- mode(Id, Mode), name(Id, Name).
file_read(Name) :- file_read_id(Id), name(Id, Name).
file_written(Name) :- file_written_id(Id), name(Id, Name).
hash(Name, Hash, Moment) :- hash_id(Id, Hash, Moment), name(Id, Name).
changed(Name) :- changed_id(Id), name(Id, Name).

%
% NAME-BASED INFERENCE RULES
%

activation_stack(Called, Callers) :- activation_stack_id(Called_id, Caller_ids), name(Called_id, Called), name(Caller_ids, Callers).
indirect_activation(Caller, Called) :- indirect_activation_id(Caller_id, Called_id), name(Called_id, Called), name(Caller_id, Caller).
activation_influence(Influencer, Influenced) :- activation_influence_id(Influencer_id, Influenced_id), name(Influencer_id, Influencer), name(Influenced_id, Influenced).
access_stack(File, Functions) :- access_stack_id(File_id, Functions_id), name(File_id, File), name(Functions_id, Functions).
indirect_access(Function, File) :- indirect_access_id(Function_id, File_id), name(Function_id, Function), name(File_id, File).
access_influence(Influencer, Influenced) :- access_influence_id(Influencer_id, Influenced_id), name(Influencer_id, Influencer), name(Influenced_id, Influenced).

%
% SLICING-BASED ACCESSOR RULES
%

dep(Dependent, Supplier) :- dependency(_, Dependent, Supplier).
usage_or_assign(Name, Line, Id) :- usage(_, Id, Name, Line).
usage_or_assign(Name, Line, Id) :- variable(Id, Name, Line, _, _).

var_name(Id, Name) :- variable(Id, Name, _, _, _).
var_line(Id, Line) :- variable(Id, _, Line, _, _).
var_info(Id, variable(Id, Name, Line, Value)) :- variable(Id, Name, Line, Value, _).


%
% SLICING-BASED INFERENCE RULES
%

slice([],[]).
slice([Id|L1], L2) :- slice(Id,L3), slice(L1, L4), union(L3, L4, L2), !.
slice(Id, [Id|L1]) :- bagof(X,dep(Id, X),L2), !, slice(L2, L1).
slice(Id, [Id]).

slice_name(Id, Names) :- slice(Id, X), maplist(var_name, X, Names).
slice_line(Id, Lines) :- slice(Id, X), maplist(var_line, X, Lines).
slice_info(Id, Infos) :- slice(Id, X), maplist(var_info, X, Infos).
