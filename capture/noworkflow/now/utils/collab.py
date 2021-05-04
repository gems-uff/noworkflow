# Copyright (c) 2016 Universidade Federal Fluminense (UFF)
# Copyright (c) 2016 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.

from ..persistence.lightweight import ActivationLW,ArgumentLW,CodeBlockLW,CodeComponentLW,CompositionLW,DependencyLW,EnvironmentAttrLW
from ..persistence.lightweight import EvaluationLW,FileAccessLW,MemberLW,ModuleLW,TrialLW,BundleLW

from ..persistence.models import Trial,Activation,Argument,CodeBlock,CodeComponent,Composition,Dependency,EnvironmentAttr,Evaluation
from ..persistence.models import FileAccess,Member,Module,Tag
from ..persistence.lightweight import ObjectStore
def store_trial_from_experiment(trial,experiment,trial_store):
    trial.experiment_id=experiment
    trial_store.add_from_object(trial)

def import_bundle(bundle, experiment):
    trials_store=ObjectStore(TrialLW)
    codeBlock_store=ObjectStore(CodeBlockLW)
    arguments_store=ObjectStore(ArgumentLW)
    codeComponent_store=ObjectStore(CodeComponentLW)
    activation_store=ObjectStore(ActivationLW)
    composition_store=ObjectStore(CompositionLW)
    dependency_store=ObjectStore(DependencyLW)
    env_store=ObjectStore(EnvironmentAttrLW)
    evaluation_store=ObjectStore(EvaluationLW)
    fileAccess_store=ObjectStore(FileAccessLW)
    member_store=ObjectStore(MemberLW)
    module_store=ObjectStore(ModuleLW)

    [store_trial_from_experiment(x,experiment,trials_store) for x in bundle.trials]
    [codeBlock_store.add_from_object(x) for x in bundle.codeBlocks]
    [arguments_store.add_from_object(x) for x in bundle.arguments]
    [codeComponent_store.add_from_object(x) for x in bundle.codeComponents]
    [activation_store.add_from_object(x) for x in bundle.activations]
    [composition_store.add_from_object(x) for x in bundle.compositions]
    [dependency_store.add_from_object(x) for x in bundle.dependencies]
    [env_store.add_from_object(x) for x in bundle.environmentAttrs]
    [evaluation_store.add_from_object(x) for x in bundle.evaluations]
    [fileAccess_store.add_from_object(x) for x in bundle.fileAccesses]
    [member_store.add_from_object(x) for x in bundle.members]
    [module_store.add_from_object(x) for x in bundle.modules]

    trials_store.do_store()
    arguments_store.do_store()
    codeBlock_store.do_store()
    codeComponent_store.do_store()
    activation_store.do_store()
    composition_store.do_store()
    dependency_store.do_store()
    env_store.do_store()
    evaluation_store.do_store()
    fileAccess_store.do_store()
    member_store.do_store()
    module_store.do_store()
    
    for x in bundle.trials:
        main_block=[c for c in bundle.codeBlocks if c.trial_id==x.id and x.main_id==c.id]
        main_block_code_hash=None
        if len(main_block)>0:
            main_block_code_hash=main_block[0].code_hash
        Tag.create_automatic_tag(x.id,main_block_code_hash,x.command, experiment_id=experiment)
    
def export_bundle(trialIds):
    #Load dependencies
    trialsToImport=[t for t in Trial.all() if t.id in trialIds ]
    actsToImport=Activation.load_by_trials(trialIds)
    argsToImport=Argument.load_by_trials(trialIds)
    codeBlockToImport=CodeBlock.load_by_trials(trialIds)
    codeComponentToImport=CodeComponent.load_by_trials(trialIds)
    compositionToImport=Composition.load_by_trials(trialIds)
    dependencyToImport=Dependency.load_by_trials(trialIds)
    envToImport=EnvironmentAttr.load_by_trials(trialIds)
    evaluationToImport=Evaluation.load_by_trials(trialIds)
    fileAccessToImport=FileAccess.load_by_trials(trialIds)
    memberToImport=Member.load_by_trials(trialIds)
    moduleToImport=Module.load_by_trials(trialIds)
    
    bundle=BundleLW()
    #Converting to LW Objects
    bundle.trials.extend(
        [TrialLW(x.id,x.script,x.start,x.finish,x.command,x.path,x.status,x.modules_inherited_from_trial_id,\
        x.parent_id,x.main_id) for x in trialsToImport]
    )
    bundle.arguments.extend(
        [ArgumentLW(x.id,x.trial_id,x.name,x.value) for x in argsToImport]
    )
    bundle.codeBlocks.extend(
        [CodeBlockLW(x.id,x.trial_id,x.code_hash,False,x.docstring,x.code_hash) for x in codeBlockToImport]
    )
    bundle.codeComponents.extend(
        [CodeComponentLW(x.id,x.trial_id,x.name,x.type,x.mode,x.first_char_line, x.first_char_column, \
            x.last_char_line,x.last_char_column,x.container_id) for x in codeComponentToImport]
    )
    bundle.activations.extend(
        [ActivationLW(x,x.trial_id,x.name,x.start_checkpoint,x.code_block_id,x.id) for x in actsToImport]
    )
    bundle.compositions.extend(
        [CompositionLW(x.id,x.trial_id,x.part_id,x.whole_id,x.type,x.position,x.extra) for x in compositionToImport]
    )
    bundle.dependencies.extend(
        [DependencyLW(x.id,x.trial_id,x.dependent_activation_id,x.dependent_id,x.dependency_activation_id,x.dependency_id,\
            x.type,x.reference,x.collection_activation_id,x.collection_id,x.key) for x in dependencyToImport]
    )
    bundle.environmentAttrs.extend(
        [EnvironmentAttrLW(x.id,x.trial_id,x.name,x.value) for x in envToImport]
    )
    bundle.evaluations.extend(
        [EvaluationLW(x.id,x.trial_id,x.code_component_id,x.activation_id,x.checkpoint,x.repr) for x in evaluationToImport]
    )
    bundle.fileAccesses.extend(
        [FileAccessLW(x.id,x.trial_id,x.name,x.checkpoint,x.mode,x.buffering,\
        x.content_hash_before,x.content_hash_after,x.activation_id) for x in fileAccessToImport]
    )
    bundle.members.extend(
        [MemberLW(x.id,x.trial_id,x.collection_activation_id,x.collection_id,x.member_activation_id,\
        x.member_id,x.key,x.checkpoint,x.type) for x in memberToImport]
    )
    bundle.modules.extend(
        [ModuleLW(x.id,x.trial_id,x.name,x.version,x.path,x.code_block_id,x.transformed) for x in moduleToImport]
    )
    return bundle