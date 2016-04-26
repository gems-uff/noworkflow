%
% ID-BASED ACCESSOR RULES FOR activation AND access predicates
%

%
% RULE DEFINITION: name(TrialId, Id, Name)/3
% DESCRIPTION: get the *Name* of an activation or access (*Id*)
%              in a given trial (*TrialId*).
%              Note that accesses Ids start with a 'f'.
%
name(_, [], []).
name(TrialId, [Id|Ids], [Name|Names]) :- name(TrialId, Id, Name), name(TrialId, Ids, Names).
name(TrialId, Id, Name) :- activation(TrialId, Id, Name, _, _, _, _).
name(TrialId, Id, Name) :- access(TrialId, Id, Name, _, _, _, _, _).

%
% RULE DEFINITION: timestamp_id(TrialId, Id, Timestamp, start|finish)/4
% DESCRIPTION: get the *Timestamp* of an activation (*Id*)
%              in a given trial (*TrialId*).
%
timestamp_id(TrialId, Id, Start, start) :- activation(TrialId, Id, _, _, Start, _, _).
timestamp_id(TrialId, Id, Finish, finish) :- activation(TrialId, Id, _, _, _, Finish, _).

%
% RULE DEFINITION: timestamp_id(TrialId, Id, Timestamp)/3
% DESCRIPTION: get the *Timestamp* of an access (*Id*)
%              in a given trial (*TrialId*).
%
timestamp_id(TrialId, Id, Timestamp) :- access(TrialId, Id, _, _, _, _, Timestamp, _).

%
% RULE DEFINITION: duration_id(TrialId, Id, Duration)/3
% DESCRIPTION: get the *Duration* of an activation (*Id*)
%              in a given trial (*TrialId*).
%
duration_id(TrialId, Id, Duration) :- timestamp_id(TrialId, Id, Start, start), timestamp_id(TrialId, Id, Finish, finish), Duration is Finish - Start.

%
% RULE DEFINITION: successor_id(TrialId, Before, After)/3
% DESCRIPTION: match activations or accesses that ocurred *Before*
%              other activations or accesses (*After*)
%              in a given trial (*TrialId*).
%              Note that called activations are successors of the caller
%
successor_id(TrialId, Before, After) :- timestamp_id(TrialId, Before, TS1, start), timestamp_id(TrialId, After, TS2, finish), TS1 =< TS2.
successor_id(TrialId, Before, After) :- timestamp_id(TrialId, Before, TS1), timestamp_id(TrialId, After, TS2), TS1 =< TS2.

%
% RULE DEFINITION: activation_id(TrialId, Caller, Called)/3
% DESCRIPTION: match *Called* activations by *Caller*
%              in a given trial (*TrialId*).
%
activation_id(TrialId, Caller, Called) :- activation(TrialId, Called, _, _, _, _, Caller).

%
% RULE DEFINITION: mode_id(TrialId, Id, Mode)/3
% DESCRIPTION: match *Mode* of an access (*Id*)
%              in a given trial (*TrialId*).
%
mode_id(TrialId, Id, Mode) :- access(TrialId, Id, _, Mode, _, _, _, _).

%
% RULE DEFINITION: read_mode(Mode)/1
% DESCRIPTION: read modes: r, a, +
%
read_mode(Mode) :- sub_atom(Mode, _, _, _, 'r').
read_mode(Mode) :- sub_atom(Mode, _, _, _, '+').

%
% RULE DEFINITION: write_mode(Mode)/1
% DESCRIPTION: write modes: w, x, a, +
%
write_mode(Mode) :- sub_atom(Mode, _, _, _, 'w').
write_mode(Mode) :- sub_atom(Mode, _, _, _, 'x').
write_mode(Mode) :- sub_atom(Mode, _, _, _, 'a').
write_mode(Mode) :- sub_atom(Mode, _, _, _, '+').

%
% RULE DEFINITION: file_read_id(TrialId, Id)/2
% DESCRIPTION: match read accesses (*Id*)
%              in a given trial (*TrialId*).
%
file_read_id(TrialId, Id) :- mode_id(TrialId, Id, Mode), once(read_mode(Mode)).

%
% RULE DEFINITION: file_written_id(TrialId, Id)/2
% DESCRIPTION: match written accesses (*Id*)
%              in a given trial (*TrialId*).
%
file_written_id(TrialId, Id) :- mode_id(TrialId, Id, Mode), once(write_mode(Mode)).

%
% RULE DEFINITION: hash_id(TrialId, Id, Hash, before|after)/4
% DESCRIPTION: match *Hash* of accesses (*Id*)
%              in a given trial (*TrialId*).
%
hash_id(TrialId, Id, Hash, before) :- access(TrialId, Id, _, _, Hash, _, _, _).
hash_id(TrialId, Id, Hash, after) :- access(TrialId, Id, _, _, _, Hash, _, _).

%
% RULE DEFINITION: changed_id(TrialId, Id)/2
% DESCRIPTION: match accesses (*Id*) that changed a file
%              in a given trial (*TrialId*).
%
changed_id(TrialId, Id) :- hash_id(TrialId, Id, Hash1, before), hash_id(TrialId, Id, Hash2, after), Hash1 \== Hash2.

%
% RULE DEFINITION: access_id(TrialId, ActivationId, Id)/3
% DESCRIPTION: match accesses (*Id*) to activations (*ActivationId*)
%              in a given trial (*TrialId*).
%
access_id(TrialId, ActivationId, Id) :- access(TrialId, Id, _, _, _, _, _, ActivationId).


%
% ID-BASED INFERENCE RULES
%


%
% RULE DEFINITION: activation_stack_id(TrialId, Called, Stack)/3
% DESCRIPTION: match caller *Stack* from a *Called* activation
%              in a given trial (*TrialId*).
%
activation_stack_id(TrialId, Called, []) :- activation_id(TrialId, nil, Called).
activation_stack_id(TrialId, Called, [Caller|Callers]) :- activation_id(TrialId, Caller, Called), activation_stack_id(TrialId, Caller, Callers).

%
% RULE DEFINITION: indirect_activation_id(TrialId, Caller, Called)/3
% DESCRIPTION: match *Caller* activations that belongs to *Called* stack
%              in a given trial (*TrialId*).
%
indirect_activation_id(TrialId, Caller, Called) :- activation_stack_id(TrialId, Called, Callers), member(Caller, Callers).

%
% RULE DEFINITION: activation_influence_id(TrialId, Influencer, Influenced)/3
% DESCRIPTION: match *Influencer* activations that might have *Influenced* an activation
%              in a given trial (*TrialId*).
%              This a Naive rule! It considers just the succession order
%
activation_influence_id(TrialId, Influencer, Influenced) :- successor_id(TrialId, Influencer, Influenced).

%
% RULE DEFINITION: access_stack_id(TrialId, File, Stack)/3
% DESCRIPTION: match *File* accesses from an activation *Stack*
%              in a given trial (*TrialId*).
%
access_stack_id(TrialId, File, [Function|Functions]) :- access_id(TrialId, Function, File), activation_stack_id(TrialId, Function, Functions).

%
% RULE DEFINITION: indirect_access_id(TrialId, Activation, File)/3
% DESCRIPTION: match *File* accesses that belongs to an *Activation* stack
%              in a given trial (*TrialId*).
%
indirect_access_id(TrialId, Function, File) :- access_stack_id(TrialId, File, Functions), member(Function, Functions).

%
% RULE DEFINITION: activation_influence_id(TrialId, Influencer, Influenced)/3
% DESCRIPTION: match *Influencer* activations that might have *Influenced* an access
%              in a given trial (*TrialId*).
%              This a Naive rule! It considers just the succession order
%
access_influence_id(TrialId, Influencer, Influenced) :- file_read_id(TrialId, Influencer), file_written_id(TrialId, Influenced), successor_id(TrialId, Influencer, Influenced), access_id(TrialId, F1, Influencer), access_id(TrialId, F2, Influenced), activation_influence_id(TrialId, F1, F2).

%
% NAME-BASED ACCESSOR RULES
%

%
% RULE DEFINITION: timestamp(TrialId, Name, Timestamp, start|finish)/4
% DESCRIPTION: get the *Timestamp* of an activation by *Name*
%              in a given trial (*TrialId*).
%
timestamp(TrialId, Name, Timestamp, Moment) :- timestamp_id(TrialId, Id, Timestamp, Moment), name(TrialId, Id, Name).

%
% RULE DEFINITION: timestamp(TrialId, Name, Timestamp)/3
% DESCRIPTION: get the *Timestamp* of an access by *Name*
%              in a given trial (*TrialId*).
%
timestamp(TrialId, Name, Timestamp) :- timestamp_id(TrialId, Id, Timestamp), name(TrialId, Id, Name).

%
% RULE DEFINITION: duration(TrialId, Name, Duration)/3
% DESCRIPTION: get the *Duration* of an activation by *Name*
%              in a given trial (*TrialId*).
%
duration(TrialId, Name, Duration) :- duration_id(TrialId, Id, Duration), name(TrialId, Id, Name).

%
% RULE DEFINITION: successor(TrialId, Before, After)/3
% DESCRIPTION: match activations or accesses by name that ocurred *Before*
%              other activations or accesses by name (*After*)
%              in a given trial (*TrialId*).
%              Note that called activations are successors of the caller
%
successor(TrialId, Before, After) :- successor_id(TrialId, BeforeId, AfterId), name(TrialId, BeforeId, Before), name(TrialId, AfterId, After).

%
% RULE DEFINITION: mode(TrialId, Name, Mode)/3
% DESCRIPTION: match *Mode* of an access by file *Name*
%              in a given trial (*TrialId*).
%
mode(TrialId, Name, Mode) :- mode_id(TrialId, Id, Mode), name(TrialId, Id, Name).

%
% RULE DEFINITION: file_read(TrialId, Name)/2
% DESCRIPTION: match read accesses by *Name*
%              in a given trial (*TrialId*).
%
file_read(TrialId, Name) :- file_read_id(TrialId, Id), name(TrialId, Id, Name).

% RULE DEFINITION: file_written(TrialId, Name)/2
% DESCRIPTION: match written accesses by *Name*
%              in a given trial (*TrialId*).
%
file_written(TrialId, Name) :- file_written_id(TrialId, Id), name(TrialId, Id, Name).

%
% RULE DEFINITION: hash(TrialId, Name, Hash, before|after)/4
% DESCRIPTION: match *Hash* of accesses by *Name*
%              in a given trial (*TrialId*).
%
hash(TrialId, Name, Hash, Moment) :- hash_id(TrialId, Id, Hash, Moment), name(TrialId, Id, Name).

%
% RULE DEFINITION: changed(TrialId, Name)/2
% DESCRIPTION: match accesses by *Name* that changed a file
%              in a given trial (*TrialId*).
%
changed(TrialId, Name) :- changed_id(TrialId, Id), name(TrialId, Id, Name).

%
% NAME-BASED INFERENCE RULES
%

%
% RULE DEFINITION: activation_stack(TrialId, Called, Callers)/3
% DESCRIPTION: match caller *Stack* from a *Called* activation by name
%              in a given trial (*TrialId*).
%
activation_stack(TrialId, Called, Callers) :- activation_stack_id(TrialId, CalledId, CallerIds), name(TrialId, CalledId, Called), name(TrialId, CallerIds, Callers).

% RULE DEFINITION: indirect_activation(TrialId, Caller, Called)/3
% DESCRIPTION: match *Caller* activations by name that belongs to *Called* stack
%              in a given trial (*TrialId*).
%
indirect_activation(TrialId, Caller, Called) :- indirect_activation_id(TrialId, CallerId, CalledId), name(TrialId, CalledId, Called), name(TrialId, CallerId, Caller).

%
% RULE DEFINITION: activation_influence(TrialId, Influencer, Influenced)/3
% DESCRIPTION: match *Influencer* activations by name that might have *Influenced* an activation
%              in a given trial (*TrialId*).
%              This a Naive rule! It considers just the succession order
%
activation_influence(TrialId, Influencer, Influenced) :- activation_influence_id(TrialId, InfluencerId, InfluencedId), name(TrialId, InfluencerId, Influencer), name(TrialId, InfluencedId, Influenced).

%
% RULE DEFINITION: access_stack(TrialId, File, Stack)/3
% DESCRIPTION: match *File* accesses by name from an activation *Stack*
%              in a given trial (*TrialId*).
%
access_stack(TrialId, File, Activations) :- access_stack_id(TrialId, FileId, ActivationsId), name(TrialId, FileId, File), name(TrialId, ActivationsId, Activations).

%
% RULE DEFINITION: indirect_access(TrialId, Activation, File)/3
% DESCRIPTION: match *File* accesses by name that belongs to an *Activation* stack
%              in a given trial (*TrialId*).
%
indirect_access(TrialId, Activation, File) :- indirect_access_id(TrialId, Activationid, FileId), name(TrialId, Activationid, Activation), name(TrialId, FileId, File).

%
% RULE DEFINITION: access_influence(TrialId, Influencer, Influenced)/3
% DESCRIPTION: match *Influencer* activations by name that might have *Influenced* an access
%              in a given trial (*TrialId*).
%              This a Naive rule! It considers just the succession order
%
access_influence(TrialId, Influencer, Influenced) :- access_influence_id(TrialId, InfluencerId, InfluencedId), name(TrialId, InfluencerId, Influencer), name(TrialId, InfluencedId, Influenced).

%
% SLICING-BASED ACCESSOR RULES
%

%
% RULE DEFINITION: dep(TrialId, Dependent, Supplier)/3
% DESCRIPTION: match *Dependent* variables to *Supplier* variables
%              in a given trial (*TrialId*).
%
dep(TrialId, Dependent, Supplier) :- dependency(TrialId, _, _, Dependent, _, Supplier).

%
% RULE DEFINITION: usage_or_assign(TrialId, Name, Line, Id)/4
% DESCRIPTION: match *Name* and *Line* of variable (*Id*) usages or assignments
%              in a given trial (*TrialId*).
%
usage_or_assign(TrialId, Name, Line, Id) :- usage(TrialId, _, Id, _, Name, Line).
usage_or_assign(TrialId, Name, Line, Id) :- variable(TrialId, _, Id, Name, Line, _, _).

%
% RULE DEFINITION: var_name(TrialId, Id, Name)/3
% DESCRIPTION: match *Name* of variable (*Id*)
%              in a given trial (*TrialId*).
%
var_name(TrialId, Id, Name) :- variable(TrialId, _, Id, Name, _, _, _).

%
% RULE DEFINITION: var_line(TrialId, Id, Line)/3
% DESCRIPTION: match *Line* of variable (*Id*)
%              in a given trial (*TrialId*).
%
var_line(TrialId, Id, Line) :- variable(TrialId, _, Id, _, Line, _, _).

%
% RULE DEFINITION: var_info(TrialId, Id, Variable)/3
% DESCRIPTION: get *Variable* by variable *Id*
%              in a given trial (*TrialId*).
%
var_info(TrialId, Id, variable(TrialId, Activation, Id, Name, Line, Value, Timestamp)) :- variable(TrialId, Activation, Id, Name, Line, Value, Timestamp).


%
% SLICING-BASED INFERENCE RULES
%

%
% RULE DEFINITION: slice(TrialId, Dependent, Dependencies)/3
% DESCRIPTION: get *Dependencies* of *Dependent* variable
%              in a given trial (*TrialId*).
%
slice(_, [],[]).
slice(TrialId, [Id|L1], L2) :- slice(TrialId, Id, L3), slice(TrialId, L1, L4), union(L3, L4, L2), !.
slice(TrialId, Id, [Id|L1]) :- bagof(X, dep(TrialId, Id, X),L2), !, slice(TrialId, L2, L1).
slice(_, Id, [Id]).

%
% RULE DEFINITION: variable_name_dependencies(TrialId, Dependent, Names)/3
% DESCRIPTION: get name *Dependencies* of *Dependent* variable
%              in a given trial (*TrialId*).
%
variable_name_dependencies(TrialId, Id, Names) :- slice(TrialId, Id, X), maplist(var_name(TrialId), X, Names).

%
% RULE DEFINITION: variable_line_dependencies(TrialId, Dependent, Lines)/3
% DESCRIPTION: get line *Dependencies* of *Dependent* variable
%              in a given trial (*TrialId*).
%
variable_line_dependencies(TrialId, Id, Lines) :- slice(TrialId, Id, X), maplist(var_line(TrialId), X, Lines).

%
% RULE DEFINITION: variable_dependencies_info(TrialId, Dependent, Infos)/3
% DESCRIPTION: get variable *Dependencies* of *Dependent* variable
%              in a given trial (*TrialId*).
%
variable_dependencies_info(TrialId, Id, Infos) :- slice(TrialId, Id, X), maplist(var_info(TrialId), X, Infos).


%
% RULE DEFINITION: variables_variables_dependency(TrialId, Dependents, Dependencies)/3
% DESCRIPTION: match *Dependencies* of *Dependents*
%              in a given trial (*TrialId*).
%
variables_variables_dependency(_, [],[]).
variables_variables_dependency(TrialId, [Dependent|Dependents], Dependencies) :- variable_variables_dependency(TrialId, Dependent, SomeDependencies),
                                                                                 variables_variables_dependency(TrialId, Dependents, OtherDependencies),
                                                                                 ord_union(SomeDependencies, OtherDependencies, Dependencies).

%
% RULE DEFINITION: variable_variables_dependency(TrialId, Dependent, Dependencies)/3
% DESCRIPTION: match *Dependencies* of a *Dependent*
%              in a given trial (*TrialId*).
%
variable_variables_dependency(TrialId, Dependent, Dependencies) :- variable(TrialId, _, Dependent, _, _, _, _),
                                                                   findall(Dependency, dependency(TrialId, _, _, Dependent, _, Dependency), DirectDependenciesWithDuplicates),
                                                                   sort(DirectDependenciesWithDuplicates, DirectDependencies),
                                                                   variables_variables_dependency(TrialId, DirectDependencies, IndirectDependencies),
                                                                   ord_union(DirectDependencies, IndirectDependencies, Dependencies).

%
% RULE DEFINITION: variables_activations_dependency(TrialId, DependentVariables, DependencyActivations)/3
% DESCRIPTION: match *DependencyActivations* of *DependentVariables*
%              in a given trial (*TrialId*).
%
variables_activations_dependency(_, [], []).
variables_activations_dependency(TrialId, [DependentVariable|DependentVariables], DependencyActivations) :- variable_activations_dependency(TrialId, DependentVariable, SomeDependencyActivations),
                                                                                                            variables_activations_dependency(TrialId, DependentVariables, OtherDependencyActivations),
                                                                                                            ord_union(SomeDependencyActivations, OtherDependencyActivations, DependencyActivations).
%
% RULE DEFINITION: variable_activations_dependency(TrialId, DependentVariable, DependencyActivations)/3
% DESCRIPTION: match *DependencyActivations* of a *DependentVariable*
%              in a given trial (*TrialId*).
%
%variable_activations_dependency(TrialId, DependentVariable, DependencyActivations)
variable_activations_dependency(TrialId, DependentVariable, DependencyActivations) :- variable_variables_dependency(TrialId, DependentVariable, DependencyVariables),
                                                                                      findall(DependencyActivation, (member(DependencyVariable, DependencyVariables), variable(TrialId, DependencyActivation, DependencyVariable, _, _, _, _)), DependencyActivationsWithDuplicates),
                                                                                      sort(DependencyActivationsWithDuplicates, DependencyActivations).

%
% RULE DEFINITION: activation_activations_dependency(TrialId, Dependent, Dependencies)/3
% DESCRIPTION: match *Dependencies* of a *Dependent* activation
%              in a given trial (*TrialId*).
%
activation_activations_dependency(TrialId, DependentActivation, DependencyActivations) :- findall(DependentVariable, variable(TrialId, DependentActivation, DependentVariable, _, _, _, _), DependentVariablesWithDuplicates),
                                                                                          sort(DependentVariablesWithDuplicates, DependentVariables),
                                                                                          variables_activations_dependency(TrialId, DependentVariables, AllDependencyActivations),
                                                                                          ord_subtract(AllDependencyActivations, [DependentActivation], DependencyActivations).