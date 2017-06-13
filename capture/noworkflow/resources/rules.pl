% ToDo: test all access rules
% ToDo: evaluation influence activation
%   Check if an evaluation influence any other evaluation inside an activation
% ToDo: activation influence activation
%   Check if any evaluation of an activation influence any other evaluation inside another activation
% ToDo: activation influence evaluation
%   Check if any evaluation of an activation influence a evaluation
% ToDo: optimize evaluation_influence


%%% ID RULES

    % compartment_id(WholeId, PartId, CombinedId)/3
        % DESCRIPTION: get the *CombinedId* of a compartment defined by *WholeId* and *PartId*

        compartment_id(WholeId, PartId, [WholeId, PartId]).

    % evaluation_code_id(TrialId, Id, CodeId)/3
        % DESCRIPTION: match *CodeId* of evalation *Id*
        %              in a given trial (*TrialId*).

        evaluation_code_id(TrialId, Id, CodeId) :- evaluation(TrialId, Id, _, CodeId, _, _).


%%% NAME RULES

    % code_name(TrialId, Id, Name)/3
        % DESCRIPTION: get the *Name* of a code_component or code_block (*Id*)
        %              in a given trial (*TrialId*).

        code_name(_, [], []).
        code_name(TrialId, [Id|Ids], [Name|Names]) :- code_name(TrialId, Id, Name), code_name(TrialId, Ids, Names).
        code_name(TrialId, Id, Name) :- code_component(TrialId, Id, Name, _, _, _, _, _, _, _).

    % evaluation_name(TrialId, Id, Name)/3
        % DESCRIPTION: get the *Name* of an evaluation or activation (*Id*)
        %              in a given trial (*TrialId*).

        evaluation_name(_, [], []).
        evaluation_name(TrialId, [Id|Ids], [Name|Names]) :- evaluation_name(TrialId, Id, Name), evaluation_name(TrialId, Ids, Names).
        evaluation_name(TrialId, Id, Name) :- evaluation_code_id(TrialId, Id, CodeId), code_name(TrialId, CodeId, Name).

    % activation_name(TrialId, Id, Name)/3
        % DESCRIPTION: get the *Name* of an activation (*Id*)
        %              in a given trial (*TrialId*).
        %              Note that it may be different than the evaluation_name

        activation_name(_, [], []).
        activation_name(TrialId, [Id|Ids], [Name|Names]) :- activation_name(TrialId, Id, Name), activation_name(TrialId, Ids, Names).
        activation_name(TrialId, Id, Name) :- activation(TrialId, Id, Name, _, _).

    % access_name(TrialId, Id, Name)/3
        % DESCRIPTION: get the *Name* of an access (*Id*)
        %              in a given trial (*TrialId*).

        access_name(_, [], []).
        access_name(TrialId, [Id|Ids], [Name|Names]) :- access_name(TrialId, Id, Name), access_name(TrialId, Ids, Names).
        access_name(TrialId, Id, Name) :- access(TrialId, Id, Name, _, _, _, _, _).

    % value_name(TrialId, Id, Name)/3
        % DESCRIPTION: get the *Name* (Value) of a value (*Id*)
        %              in a given trial (*TrialId*).

        value_name(_, [], []).
        value_name(TrialId, [Id|Ids], [Name|Names]) :- value_name(TrialId, Id, Name), value_name(TrialId, Ids, Names).
        value_name(TrialId, Id, Name) :- value(TrialId, Id, Name, _).

    % compartment_name(TrialId, [WholeId, PartId], Name)/3
        % DESCRIPTION: get the *Name* of a compartment ([*WholeId*, *PartId*])
        %              in a given trial (*TrialId*).

        compartment_name(_, [], []).
        compartment_name(TrialId, [Id|Ids], [Name|Names]) :- compartment_name(TrialId, Id, Name), compartment_name(TrialId, Ids, Names).
        compartment_name(TrialId, [WholeId, PartId], Name) :- compartment(TrialId, Name, _, WholeId, PartId).

    % name(TrialId, Model, Id, Name)/4
        % DESCRIPTION: get the *Name* of a *Model* (*Id*)
        %              in a given trial (*TrialId*).

        name(TrialId, code_component, Id, Name) :- code_name(TrialId, Id, Name).
        name(TrialId, code_block, Id, Name) :- code_name(TrialId, Id, Name).
        name(TrialId, evaluation, Id, Name) :- evaluation_name(TrialId, Id, Name).
        name(TrialId, activation, Id, Name) :- activation_name(TrialId, Id, Name).
        name(TrialId, access, Id, Name) :- access_name(TrialId, Id, Name).
        name(TrialId, value, Id, Name) :- value_name(TrialId, Id, Name).
        name(TrialId, compartment, Id, Name) :- compartment_name(TrialId, Id, Name).
        name(TrialId, trial, 0, Name) :- trial(TrialId, Name, _, _, _, _, _, _, _).

    % map_names(TrialId, Model, Ids, Names)/4
        % DESCRIPTION: get the *Names* of instances (*Ids*) of a *Model*
        %              in a given trial (*TrialId*).

        map_names(TrialId, Model, Ids, Names) :- maplist(name(TrialId, Model), Ids, Names).


%%% TIMESTAMP RULES

    % timestamp_id(TrialId, Id, Timestamp, ModelMoment)/4
        % DESCRIPTION: get the *Timestamp* of a *ModelMoment* (*Id*)
        %              in a given trial (*TrialId*).
        %              ModelMoment:
        %                start: start time of an activation (equivalent to *activation*)
        %                finish: finish time of an activation (equivalent to *evaluation*)
        %                evaluation: evaluation timestamp
        %                activation: activation timestamp
        %                access: access timestamp
        %              Use Id == 0 to match the trial itself
        %              Use Id == [WholeId, PartId] to match compartments

        timestamp_id(TrialId, 0, Start, start) :- trial(TrialId, _, Start, _, _, _, _, _, _).
        timestamp_id(TrialId, 0, Finish, finish) :- trial(TrialId, _, _, Finish, _, _, _, _, _).
        timestamp_id(TrialId, Id, Start, start) :- timestamp_id(TrialId, Id, Start, activation).
        timestamp_id(TrialId, Id, Finish, finish) :- timestamp_id(TrialId, Id, Finish, evaluation).
        timestamp_id(TrialId, Id, Moment, activation) :- activation(TrialId, Id, _, Moment, _).
        timestamp_id(TrialId, Id, Moment, evaluation) :- evaluation(TrialId, Id, Moment, _, _, _).
        timestamp_id(TrialId, Id, Moment, access) :- access(TrialId, Id, _, _, _, _, Moment, _).
        timestamp_id(TrialId, [WholeId, PartId], Moment, compartment) :- compartment(TrialId, _, Moment, WholeId, PartId).

    % duration_id(TrialId, Id, Duration)/3
        % DESCRIPTION: get the *Duration* of an activation (*Id*)
        %              in a given trial (*TrialId*).

        duration_id(TrialId, Id, Duration) :- timestamp_id(TrialId, Id, Start, start), timestamp_id(TrialId, Id, Finish, finish), Duration is Finish - Start.

    % successor_id(TrialId, BeforeModel, BeforeId, AfterModel, AfterId)/5
        % DESCRIPTION: match *BeforeModel* instance (*BeforeId*) that ocurred
        %              before other *AfterModel* instance (*AfterId*)
        %              in a given trial (*TrialId*).
        %              Note that called activations are successors of the caller

        successor_id(TrialId, BeforeModel, BeforeId, AfterModel, AfterId) :- timestamp_id(TrialId, BeforeId, TS1, BeforeModel), timestamp_id(TrialId, AfterId, TS2, AfterModel), AfterModel \= activation, TS1 =< TS2.
        successor_id(TrialId, trial, 0, AfterModel, AfterId) :- successor_id(TrialId, start, 0, AfterModel, AfterId).
        successor_id(TrialId, BeforeModel, BeforeId, trial, 0) :- successor_id(TrialId, BeforeModel, BeforeId, finish, 0).
        successor_id(TrialId, BeforeModel, BeforeId, activation, Id) :- successor_id(TrialId, BeforeModel, BeforeId, evaluation, Id), activation(TrialId, Id, _, _, _).

    %%% NAME-BASED

    % timestamp(TrialId, Name, Timestamp, ModelMoment)/4
        % DESCRIPTION: get the *Timestamp* of a *ModelMoment* instance by *Name*
        %              in a given trial (*TrialId*).

        timestamp(TrialId, Name, Timestamp, Model) :- timestamp_id(TrialId, Id, Timestamp, Model), name(TrialId, Model, Id, Name).
        timestamp(TrialId, trial, Timestamp, Moment) :- timestamp_id(TrialId, 0, Timestamp, Moment).
        timestamp(TrialId, Name, Timestamp, start) :- timestamp_id(TrialId, Id, Timestamp, start), name(TrialId, activation, Id, Name).
        timestamp(TrialId, Name, Timestamp, finish) :- timestamp_id(TrialId, Id, Timestamp, finish), name(TrialId, activation, Id, Name).

    % duration(TrialId, Name, Duration)/3
        % DESCRIPTION: get the *Duration* of an activation by *Name*
        %              in a given trial (*TrialId*).

        duration(TrialId, Name, Duration) :- duration_id(TrialId, Id, Duration), name(TrialId, activation, Id, Name).
        duration(TrialId, trial, Duration) :- duration_id(TrialId, 0, Duration).

    % successor(TrialId, BeforeModel, BeforeName, AfterModel, AfterName)/5
        % DESCRIPTION: match *BeforeModel* instances by *BeforeName* that ocurred before
        %              other *AfterModel* instances by *AfterName*
        %              in a given trial (*TrialId*).
        %              Note that called activations are successors of the caller

        successor(TrialId, BeforeModel, BeforeName, AfterModel, AfterName) :- successor_id(TrialId, BeforeModel, BeforeId, AfterModel, AfterId), name(TrialId, BeforeModel, BeforeId, BeforeName), name(TrialId, AfterModel, AfterId, AfterName).


%%% MODE ACCESS RULES

    % read_mode(Mode)/1
        % DESCRIPTION: read modes: r, r+, a+

        read_mode(Mode) :- sub_atom(Mode, _, _, _, 'r').
        read_mode(Mode) :- sub_atom(Mode, _, _, _, '+').

    % write_mode(Mode)/1
        % DESCRIPTION: write modes: w, x, a, +

        write_mode(Mode) :- sub_atom(Mode, _, _, _, 'w').
        write_mode(Mode) :- sub_atom(Mode, _, _, _, 'x').
        write_mode(Mode) :- sub_atom(Mode, _, _, _, 'a').
        write_mode(Mode) :- sub_atom(Mode, _, _, _, '+').

    % delete_mode(Mode)/1
        % DESCRIPTION: delete modes: d

        delete_mode(Mode) :- sub_atom(Mode, _, _, _, 'd').

    % param_mode(Mode)/1
        % DESCRIPTION: param modes: p
        %              Note: Python defines this mode for variables
        %                    but I (Joao) have never seem in practice

        param_mode(Mode) :- sub_atom(Mode, _, _, _, 'p').

    % access_mode_id(TrialId, Id, Mode)/3
        % DESCRIPTION: match *Mode* of an access (*Id*)
        %              in a given trial (*TrialId*).

        access_mode_id(TrialId, Id, Mode) :- access(TrialId, Id, _, Mode, _, _, _, _).

    % code_mode_id(TrialId, Id, Mode)/3
        % DESCRIPTION: match *Mode* of a code_component (*Id*)
        %              in a given trial (*TrialId*).

        code_mode_id(TrialId, Id, Mode) :- code_component(TrialId, Id, _, _, Mode, _, _, _, _, _).

    % mode_id(TrialId, Model, Id, Mode)/4
        % DESCRIPTION: match *Mode* of a *Model* (*Id*)
        %              in a given trial (*TrialId*).

        mode_id(TrialId, access, Id, Mode) :- access_mode_id(TrialId, Id, Mode).
        mode_id(TrialId, code_component, Id, Mode) :- code_mode_id(TrialId, Id, Mode).
        mode_id(TrialId, code_block, Id, Mode) :- code_mode_id(TrialId, Id, Mode).
        mode_id(TrialId, evaluation, Id, Mode) :- evaluation_code_id(TrialId, Id, CodeId), code_mode_id(TrialId, CodeId, Mode).
        mode_id(TrialId, activation, Id, Mode) :- evaluation_code_id(TrialId, Id, CodeId), code_mode_id(TrialId, CodeId, Mode).

    %%% NAME-BASED

    % mode(TrialId, Model, Name, Mode)/4
        % DESCRIPTION: match *Mode* of a *Model* by *Name*
        %              in a given trial (*TrialId*).

        mode(TrialId, Model, Name, Mode) :- mode_id(TrialId, Model, Id, Mode), name(TrialId, Model, Id, Name).


%%% HASH RULES

    % hash_id(TrialId, Id, Hash, before|after|code_block)/4
        % DESCRIPTION: match *Hash* of accesses (*Id*)
        %              in a given trial (*TrialId*).

        hash_id(TrialId, Id, Hash, before) :- access(TrialId, Id, _, _, Hash, _, _, _).
        hash_id(TrialId, Id, Hash, after) :- access(TrialId, Id, _, _, _, Hash, _, _).
        hash_id(TrialId, Id, Hash, code_block) :- code_block(TrialId, Id, Hash, _).

    % changed_id(TrialId, Id)/2
        % DESCRIPTION: match accesses (*Id*) that changed a file
        %              in a given trial (*TrialId*).

        changed_id(TrialId, Id) :- hash_id(TrialId, Id, Hash1, before), hash_id(TrialId, Id, Hash2, after), Hash1 \== Hash2.

    %%% NAME-BASED

    % hash(TrialId, Name, Hash, before|after|code_block)/4
        % DESCRIPTION: match *Hash* of accesses by *Name*
        %              in a given trial (*TrialId*).

        hash(TrialId, Name, Hash, Moment) :- hash_id(TrialId, Id, Hash, Moment), name(TrialId, access, Id, Name).
        hash(TrialId, Name, Hash, code_block) :- hash_id(TrialId, Id, Hash, code_block), name(TrialId, code_block, Id, Name).

    % changed(TrialId, Name)/2
        % DESCRIPTION: match accesses by *Name* that changed a file
        %              in a given trial (*TrialId*).

        changed(TrialId, Name) :- changed_id(TrialId, Id), name(TrialId, access, Id, Name).


%%% CODE_COMPONENT/CODE_BLOCK RULES

    % code_line_id(TrialId, Id, Line)/3
        % DESCRIPTION: match *Line* of an code_component *Id*
        %              in a given trial (*TrialId*).
        %              Note: Line may match multiple lines

        code_line_id(TrialId, Id, Line) :- code_component(TrialId, Id, _, _, _, FirstCharLine, _, LastCharLine, _, _), between(FirstCharLine, LastCharLine, Line).

    % map_code_lines_id(TrialId, Ids, Lines)/3
        % DESCRIPTION: get the *Lines* of code components (*Ids*)
        %              in a given trial (*TrialId*).

        map_code_lines_id(_, [], []).
        map_code_lines_id(TrialId, [Id|Ids], Lines) :- bagof(L, code_line_id(TrialId, Id, L), L1), map_code_lines_id(TrialId, Ids, L2), append(L1, L2, LT), sort(LT, Lines).


%%% ACTIVATION/EVALUATION RULES

    % is_activation_id(TrialId, Id)/2
        % DESCRIPTION: check if an evaluation *Id* is an activation Id
        %              in a given trial (*TrialId*).

        is_activation_id(TrialId, Id) :- activation(TrialId, Id, _, _, _).


    % activation_id(TrialId, Caller, Called)/3
        % DESCRIPTION: match *Called* evaluations by *Caller* activation
        %              in a given trial (*TrialId*).

        activation_id(TrialId, Caller, Called) :- evaluation(TrialId, Called, _, _, Caller, _).

    % called_activation_id(TrialId, Caller, Called)/3
        % DESCRIPTION: match *Called* activation by *Caller* activation
        %              in a given trial (*TrialId*).

        called_activation_id(TrialId, Caller, Called) :- activation_id(TrialId, Caller, Called), activation(TrialId, Called, _, _, _).

    % evaluation_line_id(TrialId, Id, Line)/3
        % DESCRIPTION: match *Line* of an evaluation *Id*
        %              in a given trial (*TrialId*).
        %              Note: Line may match multiple lines

        evaluation_line_id(TrialId, Id, Line) :- evaluation_code_id(TrialId, Id, CodeId), code_line_id(TrialId, CodeId, Line).

    % map_evaluation_lines_id(TrialId, Ids, Lines)/3
        % DESCRIPTION: get the *Lines* of evaluations (*Ids*)
        %              in a given trial (*TrialId*).

        map_evaluation_lines_id(_, [], []).
        map_evaluation_lines_id(TrialId, [Id|Ids], Lines) :- bagof(L, evaluation_line_id(TrialId, Id, L), L1), map_evaluation_lines_id(TrialId, Ids, L2), append(L1, L2, LT), sort(LT, Lines).

    % map_evaluation_code_ids(TrialId, Ids, CodeIds)/3
        % DESCRIPTION: get the *CodeIds* of evaluations (*Ids*)
        %              in a given trial (*TrialId*).

        map_evaluation_code_ids(TrialId, Ids, CodeIds) :- maplist(evaluation_code_id(TrialId), Ids, CodeIds).

    % filter_activation_ids(TrialId, Ids, ActivationIds)/3
        % DESCRIPTION: filter evaluation *Ids* to get only *ActivationIds*
        %              in a given trial (*TrialId*).

        filter_activation_ids(TrialId, Ids, ActivationIds) :- include(is_activation_id(TrialId), Ids, ActivationIds).

    % recursive_internal_evaluations_ids(TrialId, Activations, Evaluations)/3
        % DESCRIPTION: get a list of internar *Evaluations* from a list of *Activations*
        %              in a given trial (*TrialId*).

        recursive_internal_evaluations_ids(_, [], []).
        recursive_internal_evaluations_ids(TrialId, [InfluencedActivation], Evaluations) :- bagof(X, activation_id(TrialId, InfluencedActivation, X), E1), filter_activation_ids(TrialId, E1, Activations), recursive_internal_evaluations_ids(TrialId, Activations, E2), append(E1, E2, Evaluations), !.
        recursive_internal_evaluations_ids(TrialId, [A|As], Evaluations) :- recursive_internal_evaluations_ids(TrialId, [A], E1), recursive_internal_evaluations_ids(TrialId, As, E2), append(E1, E2, Evaluations).


%%% DOCSTRING RULES

    % code_docstring_id(TrialId, Id, Docstring)/3
        % DESCRIPTION: get the *Docstring* of a code block (*Id*)
        %              in a given trial (*TrialId*).

        code_docstring_id(TrialId, Id, Docstring) :- code_block(TrialId, Id, _, Docstring).

    % activation_docstring_id(TrialId, Id, Docstring)/3
        % DESCRIPTION: get the *Docstring* of a activation (*Id*)
        %              in a given trial (*TrialId*).

        activation_docstring_id(TrialId, Id, Docstring) :- activation(TrialId, Id, _, _, BlockId), code_block(TrialId, BlockId, _, Docstring).

    % docstring_id(TrialId, Model, Id, Docstring)/4
        % DESCRIPTION: get the *Docstring* of a *Model* (*Id*)
        %              in a given trial (*TrialId*).

        docstring_id(TrialId, code_block, Id, Docstring) :- code_docstring_id(TrialId, Id, Docstring).
        docstring_id(TrialId, code_component, Id, Docstring) :- code_docstring_id(TrialId, Id, Docstring).
        docstring_id(TrialId, evaluation, Id, Docstring) :- activation_docstring_id(TrialId, Id, Docstring).
        docstring_id(TrialId, activation, Id, Docstring) :- activation_docstring_id(TrialId, Id, Docstring).

    %%% NAME-BASED

    % docstring(TrialId, Model, Name, Docstring)/4
        % DESCRIPTION: get the *Docstring* of a *Model* (*Name*)
        %              in a given trial (*TrialId*).

        docstring(TrialId, Model, Name, Docstring) :- name(TrialId, Model, Id, Name), docstring_id(TrialId, Model, Id, Docstring).


%%% SCOPE RULES

    % code_scope_id(TrialId, Id, Type)/3
        % DESCRIPTION: get the *Type* of the scope of a code component (*Id*)
        %              in a given trial (*TrialId*).
        %              Type = 'project'|'script'|'class_def'|'function_def'

        code_scope_id(TrialId, Id, 'project') :- code_component(TrialId, Id, _, _, _, _, _, _, _, nil).
        code_scope_id(TrialId, Id, Type) :- code_component(TrialId, Id, _, _, _, _, _, _, _, ContainerId), code_component(TrialId, ContainerId, _, Type, _, _, _, _, _, _).

    % evaluation_scope_id(TrialId, Id, Type)/3
        % DESCRIPTION: get the *Type* of the scope of an evaluation (*Id*)
        %              in a given trial (*TrialId*).
        %              Type = 'project'|'script'|'class_def'|'function_def'

        evaluation_scope_id(TrialId, Id, Type) :- evaluation_code_id(TrialId, Id, CodeId), code_scope_id(TrialId, CodeId, Type).

    % scope_id(TrialId, Model, Id, Type)/3
        % DESCRIPTION: get the *Type* of the scope of a *Model* (*Id*)
        %              in a given trial (*TrialId*).
        %              Type = 'project'|'script'|'class_def'|'function_def'

        scope_id(TrialId, code_block, Id, Type) :- code_scope_id(TrialId, Id, Type).
        scope_id(TrialId, code_component, Id, Type) :- code_scope_id(TrialId, Id, Type).
        scope_id(TrialId, evaluation, Id, Type) :- evaluation_scope_id(TrialId, Id, Type).
        scope_id(TrialId, activation, Id, Type) :- evaluation_scope_id(TrialId, Id, Type).

    % scope(TrialId, Model, Name, Type)/3
        % DESCRIPTION: get the *Type* of the scope of a *Model* (*Name*)
        %              in a given trial (*TrialId*).
        %              Type = 'project'|'script'|'class_def'|'function_def'

        scope(TrialId, Model, Name, Type) :- name(TrialId, Model, Id, Name), scope_id(TrialId, Model, Id, Type).


%%% ACCESS RULES

    % file_read_id(TrialId, Id)/2
        % DESCRIPTION: match read accesses (*Id*)
        %              in a given trial (*TrialId*).

        file_read_id(TrialId, Id) :- mode_id(TrialId, access, Id, Mode), once(read_mode(Mode)).

    % file_written_id(TrialId, Id)/2
        % DESCRIPTION: match written accesses (*Id*)
        %              in a given trial (*TrialId*).

        file_written_id(TrialId, Id) :- mode_id(TrialId, access, Id, Mode), once(write_mode(Mode)).

    % access_id(TrialId, ActivationId, Id)/3
        % DESCRIPTION: match accesses (*Id*) to activations (*ActivationId*)
        %              in a given trial (*TrialId*).

        access_id(TrialId, ActivationId, Id) :- access(TrialId, Id, _, _, _, _, _, ActivationId).

    %%% NAME-BASED

    % file_read(TrialId, Name)/2
        % DESCRIPTION: match read accesses by *Name*
        %              in a given trial (*TrialId*).

        file_read(TrialId, Name) :- file_read_id(TrialId, Id), name(TrialId, access, Id, Name).

    % file_written(TrialId, Name)/2
        % DESCRIPTION: match written accesses by *Name*
        %              in a given trial (*TrialId*).

        file_written(TrialId, Name) :- file_written_id(TrialId, Id), name(TrialId, access, Id, Name).


%%% TEMPORAL INFERENCE RULES

    % activation_stack_id(TrialId, Called, Stack)/3
        % DESCRIPTION: match caller *Stack* from a *Called* evaluation
        %              in a given trial (*TrialId*).

        activation_stack_id(TrialId, Called, []) :- activation_id(TrialId, nil, Called).
        activation_stack_id(TrialId, Called, [Caller|Callers]) :- activation_id(TrialId, Caller, Called), activation_stack_id(TrialId, Caller, Callers).

    % indirect_activation_id(TrialId, Caller, Called)/3
        % DESCRIPTION: match *Caller* activations that belongs to *Called* stack
        %              in a given trial (*TrialId*).

        indirect_activation_id(TrialId, Caller, Called) :- activation_stack_id(TrialId, Called, Callers), member(Caller, Callers).

    % temporal_activation_influence_id(TrialId, Influencer, Influenced)/3
        % DESCRIPTION: match *Influencer* activations that might have *Influenced* an activation
        %              in a given trial (*TrialId*).
        %              This a Naive rule! It considers just the succession order

        temporal_activation_influence_id(TrialId, Influencer, Influenced) :- successor_id(TrialId, activation, Influencer, activation, Influenced).

    % access_stack_id(TrialId, File, Stack)/3
        % DESCRIPTION: match *File* accesses from an activation *Stack*
        %              in a given trial (*TrialId*).

        access_stack_id(TrialId, File, [Function|Functions]) :- access_id(TrialId, Function, File), activation_stack_id(TrialId, Function, Functions).

    % indirect_access_id(TrialId, Activation, File)/3
        % DESCRIPTION: match *File* accesses that belongs to an *Activation* stack
        %              in a given trial (*TrialId*).

        indirect_access_id(TrialId, Function, File) :- access_stack_id(TrialId, File, Functions), member(Function, Functions).

    % activation_influence_id(TrialId, Influencer, Influenced)/3
        % DESCRIPTION: match *Influencer* activations that might have *Influenced* an access
        %              in a given trial (*TrialId*).
        %              This a Naive rule! It considers just the succession order

        access_influence_id(TrialId, Influencer, Influenced) :- file_read_id(TrialId, Influencer), file_written_id(TrialId, Influenced), successor_id(TrialId, access, Influencer, access, Influenced), access_id(TrialId, F1, Influencer), access_id(TrialId, F2, Influenced), activation_influence_id(TrialId, F1, F2).

    %%% NAME-BASED

    % activation_stack(TrialId, Called, Callers)/3
        % DESCRIPTION: match caller *Stack* from a *Called* activation by name
        %              in a given trial (*TrialId*).

        activation_stack(TrialId, Called, Callers) :- activation_stack_id(TrialId, CalledId, CallerIds), name(TrialId, activation, CalledId, Called), name(TrialId, activation, CallerIds, Callers).
        activation_stack(TrialId, Called, Callers) :- activation_stack_id(TrialId, CalledId, CallerIds), name(TrialId, evaluation, CalledId, Called), name(TrialId, activation, CallerIds, Callers).

    % indirect_activation(TrialId, Caller, Called)/3
        % DESCRIPTION: match *Caller* activations by name that belongs to *Called* stack
        %              in a given trial (*TrialId*).

        indirect_activation(TrialId, Caller, Called) :- indirect_activation_id(TrialId, CallerId, CalledId), name(TrialId, evaluation, CalledId, Called), name(TrialId, activation, CallerId, Caller).
        indirect_activation(TrialId, Caller, Called) :- indirect_activation_id(TrialId, CallerId, CalledId), name(TrialId, activation, CalledId, Called), name(TrialId, activation, CallerId, Caller).

    % temporal_activation_influence(TrialId, Influencer, Influenced)/3
        % DESCRIPTION: match *Influencer* activations by name that might have *Influenced* an activation
        %              in a given trial (*TrialId*).
        %              This a Naive rule! It considers just the succession order

        temporal_activation_influence(TrialId, Influencer, Influenced) :- temporal_activation_influence_id(TrialId, InfluencerId, InfluencedId), name(TrialId, activation, InfluencerId, Influencer), name(TrialId, activation, InfluencedId, Influenced).

    % access_stack(TrialId, File, Stack)/3
        % DESCRIPTION: match *File* accesses by name from an activation *Stack*
        %              in a given trial (*TrialId*).

        access_stack(TrialId, File, Activations) :- access_stack_id(TrialId, FileId, ActivationsId), name(TrialId, access, FileId, File), name(TrialId, activation, ActivationsId, Activations).

    % indirect_access(TrialId, Activation, File)/3
        % DESCRIPTION: match *File* accesses by name that belongs to an *Activation* stack
        %              in a given trial (*TrialId*).

        indirect_access(TrialId, Activation, File) :- indirect_access_id(TrialId, Activationid, FileId), name(TrialId, activation, Activationid, Activation), name(TrialId, access, FileId, File).

    % access_influence(TrialId, Influencer, Influenced)/3
        % DESCRIPTION: match *Influencer* activations by name that might have *Influenced* an access
        %              in a given trial (*TrialId*).
        %              This a Naive rule! It considers just the succession order

        access_influence(TrialId, Influencer, Influenced) :- access_influence_id(TrialId, InfluencerId, InfluencedId), name(TrialId, access, InfluencerId, Influencer), name(TrialId, access, InfluencedId, Influenced).


%%% SLICING INFERENCE RULES

    % valid_dependency_id(TrialId, Dependent, Dependency, Type)/4
        % DESCRIPTION: *Dependent* evaluation has a *Type* dependency to *Dependency* evaluation
        %              in a given trial (*TrialId*).
        %              Ignores argument types

        valid_dependency_id(TrialId, Dependent, Dependency, Type) :- dependency(TrialId, _, Dependent, _, Dependency, Type), sub_atom(Type, 0, 3, _, Prefix), Prefix \= 'arg'.

    % evaluation_slice_id(TrialId, Dependent, Dependencies)/3
        % DESCRIPTION: get *Dependencies* of *Dependent* evaluation
        %              in a given trial (*TrialId*).

        evaluation_slice_id(_, [],[]).
        evaluation_slice_id(TrialId, [Id|L1], L2) :- evaluation_slice_id(TrialId, Id, L3), evaluation_slice_id(TrialId, L1, L4), union(L3, L4, L2), !.
        evaluation_slice_id(TrialId, Id, [Id|L1]) :- bagof(X, valid_dependency_id(TrialId, Id, X, _),L2), !, evaluation_slice_id(TrialId, L2, L1).
        evaluation_slice_id(_, Id, [Id]).

    % evaluation_slice_lines_id(TrialId, Dependent, Lines)/3
        % DESCRIPTION: get *Lines* of dependencies of *Dependent* evaluation
        %              in a given trial (*TrialId*).

        evaluation_slice_lines_id(TrialId, Dependent, Lines) :- evaluation_slice_id(TrialId, Dependent, Dependencies), map_evaluation_lines_id(TrialId, Dependencies, Lines).

    % evaluation_influence_id(TrialId, Influencer, Influenced)/3
        % DESCRIPTION: *Influenced* evaluation depends on *Influencer* evaluation
        %              in a given trial (*TrialId*).

        evaluation_influence_id(TrialId, Influencer, Influenced) :- evaluation_slice_id(TrialId, Influenced, Dependencies), member(Influencer, Dependencies).


    %%% NAME-BASED


        % evaluation_slice_id_by_name(TrialId, DependentName, Dependencies)/3
            % DESCRIPTION: get *Dependencies* ids of *DependentName* evaluation
            %              in a given trial (*TrialId*).

            evaluation_slice_id_by_name(TrialId, DependentName, Dependencies) :- name(TrialId, evaluation, Dependent, DependentName), evaluation_slice_id(TrialId, Dependent, Dependencies).


        % evaluation_slice(TrialId, DependentName, DependenciesNames)/3
            % DESCRIPTION: get *DependenciesNames* of *DependentName* evaluation
            %              in a given trial (*TrialId*).

            evaluation_slice(TrialId, DependentName, DependenciesNames) :- evaluation_slice_id_by_name(TrialId, DependentName, Dependencies), map_names(TrialId, evaluation, Dependencies, DependenciesNames).

        % evaluation_slice_lines(TrialId, DependentName, Lines)/3
            % DESCRIPTION: get *Lines* of dependencies of *DependentName* evaluation
            %              in a given trial (*TrialId*).

            evaluation_slice_lines(TrialId, DependentName, Lines) :- name(TrialId, evaluation, Dependent, DependentName), evaluation_slice_lines_id(TrialId, Dependent, Lines).

        % evaluation_influence(TrialId, InfluencerName, InfluencedName)/3
            % DESCRIPTION: *InfluencerName* evaluation depends on *InfluencedName* evaluation
            %              in a given trial (*TrialId*).

            evaluation_influence(TrialId, InfluencerName, InfluencedName) :- name(TrialId, evaluation, Influenced, InfluencedName), name(TrialId, evaluation, Influencer, InfluencerName), evaluation_influence_id(TrialId, Influencer, Influenced).
