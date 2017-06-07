

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