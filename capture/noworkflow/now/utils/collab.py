from ..persistence.lightweight import ActivationLW,ArgumentLW,CodeBlockLW,CodeComponentLW,CompositionLW,DependencyLW,EnvironmentAttrLW
from ..persistence.lightweight import EvaluationLW,FileAccessLW,MemberLW,ModuleLW,TrialLW,BundleLW

from ..persistence.models import Trial,Activation,Argument,CodeBlock,CodeComponent,Composition,Dependency,EnvironmentAttr,Evaluation
from ..persistence.models import FileAccess,Member,Module,Tag

def exportBundle(trialIds):
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
        [ActivationLW(x,x.trial_id,x.name,x.start_checkpoint,x.code_block_id) for x in actsToImport]
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