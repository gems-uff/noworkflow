% ToDo: test all access rules


%%% ID RULES

    % compartment_id(WholeId, PartId, CombinedId)/3
        % DESCRIPTION: get the *CombinedId* of a compartment defined by *WholeId* and *PartId*

        compartment_id(WholeId, PartId, [WholeId, PartId]).


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
        evaluation_name(TrialId, Id, Name) :- evaluation(TrialId, Id, _, CodeId, _, _), code_name(TrialId, CodeId, Name).

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
        % DESCRIPTION: read modes: r, a, +

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
        mode_id(TrialId, evaluation, Id, Mode) :- evaluation(TrialId, Id, _, CodeId, _, _), code_mode_id(TrialId, CodeId, Mode).
        mode_id(TrialId, activation, Id, Mode) :- evaluation(TrialId, Id, _, CodeId, _, _), code_mode_id(TrialId, CodeId, Mode).

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


%%% ACTIVATION/EVALUATION RULES

    % activation_id(TrialId, Caller, Called)/3
        % DESCRIPTION: match *Called* evaluations by *Caller* activation
        %              in a given trial (*TrialId*).

        activation_id(TrialId, Caller, Called) :- evaluation(TrialId, Called, _, _, Caller, _).

    % called_activation_id(TrialId, Caller, Called)/3
        % DESCRIPTION: match *Called* activation by *Caller* activation
        %              in a given trial (*TrialId*).

        called_activation_id(TrialId, Caller, Called) :- activation_id(TrialId, Caller, Called), activation(TrialId, Called, _, _, _).


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




