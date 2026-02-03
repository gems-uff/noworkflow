# Copyright (c) 2016 Universidade Federal Fluminense (UFF)
# Copyright (c) 2016 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""Define views for 'now vis'"""
from __future__ import (absolute_import, print_function,
                        division, unicode_literals)

import os
import io
import json

from flask import render_template, jsonify, request, send_file, Response
from io import BytesIO as IO

from ..persistence.models import Trial, Activation,Activation, Experiment, ExtendedAnnotation, Group, User, MemberOfGroup, FileAccess, Module, Remote, Evaluation, CodeComponent, Dependency
from ..persistence.lightweight import ActivationLW, BundleLW, ExperimentLW, ExtendedAnnotationLW,GroupLW,UserLW,MemberOfGroupLW, RemoteLW, EvaluationLW
from ..models.history import History
from ..models.diff import Diff
from ..models.ast.trial_ast import TrialAst
from ..models.prospective.generate import generate_prospective_prov
from ..persistence import relational, content
from ..cmd.cmd_diff import Diff as DiffCMD
from ..ipython.dotmagic import DotDisplay

import subprocess
from ..utils.collab import export_bundle, import_bundle
from ..utils.compression import gzip_compress,gzip_uncompress
from ..persistence import content
import time
import difflib
from zipfile import ZipFile
from io import BytesIO

class WebServer(object):
    """Flask WebServer"""
    # pylint: disable=too-few-public-methods
    _instance = None

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super(WebServer, cls).__new__(
                cls, *args, **kwargs)
        return cls._instance

    def __init__(self):
        from flask import Flask

        self.app = Flask(__name__)

app = WebServer().app  # pylint: disable=invalid-name
app.config['MAX_CONTENT_LENGTH'] = 1600 * 1024 * 1024

@app.after_request
def add_header(req):
    """
    Add headers to both force latest IE rendering engine or Chrome Frame,
    and also to cache the rendered page for 10 minutes.
    """
    req.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    req.headers["Pragma"] = "no-cache"
    req.headers["Expires"] = "0"
    req.headers['Cache-Control'] = 'public, max-age=0'
    return req

@app.after_request
def zipper(response):
    accept_encoding = request.headers.get('Accept-Encoding', '')
    if 'gzip' not in accept_encoding.lower():
        return response
    response.direct_passthrough = False
    if (response.status_code < 200 or
        response.status_code >= 300 or
        'Content-Encoding' in response.headers):
        return response
    response.data = gzip_compress(response.data)
    response.headers['Content-Encoding'] = 'gzip'
    response.headers['Vary'] = 'Accept-Encoding'
    response.headers['Content-Length'] = len(response.data)
    return response

def getRequestContent():
    encoding = request.headers.get('Content-Encoding', '')
    if 'gzip' in encoding.lower():
        contentData=gzip_uncompress(request.data)
        return json.loads(contentData)
    return request.get_json()

@app.route("/<path:path>")
def static_proxy(path):
    """Serve static files"""
    return app.send_static_file(path)


@app.route("/experiments/<expcode>/")
@app.route("/")
@app.route("/<tid>-<graph_mode>")  # todo
def index(tid=None, graph_mode=None,expcode=None):
    """Respond history scripts and index page as HTML"""
    # pylint: disable=unused-argument
    
    experiments=[ExperimentLW(x.name,x.id,x.description).__json__() for x in Experiment.all()]
    trialCoun=Trial.count()
    server=False
    if expcode is None:
        expcode=""
        if experiments.__len__() > 0 or trialCoun==0:
            server=True
    history = History()
    return render_template(
        "index.html",
        cwd=os.getcwd(),
        scripts=history.scripts,
        experiments=experiments,
        selectedExperiment=expcode,
        server=server
    )
    
@app.route("/experiments/<expCode>/collab/bundle", methods=['GET'])
def getBundle(expCode):
    """Return bundle with trials from trials ids"""
    if experiment_in_db(expCode=expCode):
        trialsToExport=request.args.getlist("id")
        bundle=export_bundle(trialsToExport)
        resp=bundle.__json__()
        return jsonify(resp)
    
    return return_json_error_invalid_experiment_id()

@app.route("/experiments", methods=['Post'])
def createExperiment():
    expName=request.json['name']
    expDesc=request.json['description']
    if(expName!=""):
        exp=ExperimentLW(expName,"",expDesc)
        exp=Experiment.create(exp)
        return jsonify(exp.__json__()),201
    else:
        return "Experiment name must by filled",400
def getDictValue(dicti,valueToGet):
    if(valueToGet in dicti):
        return dicti[valueToGet]
    else:
        return ""
def insertAnnotation(request,annotationLevel,relatedExperiment,relatedTrial):
    annt=getDictValue(request.json,'annotation')
    description=getDictValue(request.json,'description')
    anntFormat=getDictValue(request.json,'annotationFormat')
    anntType=getDictValue(request.json,'provenanceType')
    
    
    if(annt!="" and anntFormat!=""):
        annt=ExtendedAnnotationLW(None, annt,description, anntFormat, anntType, annotationLevel, relatedExperiment, relatedTrial)
        annt=ExtendedAnnotation.create(annt)
        return jsonify(annt.__json__()),201
    else:
        return "Annotation and annotation format must by filled",400    
@app.route("/experiments/<expCode>/extendedAnnotation", methods=['Get'])
def getExperimentAnnotation(expCode):
    annotations=ExtendedAnnotation.GetInfoByExperimentId(expCode)
    annts= [ExtendedAnnotationLW(x.id,"",x.description,x.annotationFormat,x.provenanceType,x.annotationLevel,x.relatedExperiment,"").__json__() for x in annotations]
    return jsonify(annts),200
@app.route("/trials/<trialCode>/extendedAnnotation", methods=['Get'])
def getTrialAnnotation(trialCode):
    annotations=ExtendedAnnotation.GetInfoByTrialId(trialCode)
    annts= [ExtendedAnnotationLW(x.id,"",x.description,x.annotationFormat,x.provenanceType,x.annotationLevel,"",x.relatedTrial).__json__() for x in annotations]
    return jsonify(annts),200

@app.route("/extendedAnnotation/<id>/annotation", methods=['Get'])
def getExtendedAnnotationContent(id):
    annt=ExtendedAnnotation.GetById(id)
    extention=annt.annotationFormat
    if(extention=="plainText"):
        extention="txt"
    return send_file(
        IO(bytes(annt.annotation, 'utf-8')),
        mimetype='application/octet-stream',
        as_attachment=True,
        download_name=f"{id}.{extention}"
    )


@app.route("/experiments/<expCode>/extendedAnnotation", methods=['Post'])
def createExperimentAnnotation(expCode):
    return insertAnnotation(request,"Experiment",expCode,None)
    
@app.route("/trials/<trialCode>/extendedAnnotation", methods=['Post'])
def createTrialAnnotation(trialCode):
    return insertAnnotation(request,"Trial",None,trialCode)

@app.route("/groups", methods=['Post'])
def createGroup():
    groupName=getDictValue(request.json,'name')
    
    if(groupName!=""):
        grp=GroupLW(None, groupName,None)
        grp=Group.create(grp)
        return jsonify(grp.__json__()),201
    else:
        return "Name must by filled",400 
@app.route("/groups/<grpId>", methods=['Delete'])
def deleteGroup(grpId):
    Group.delete(grpId)
    return "",200

@app.route("/groups/<grpId>/users", methods=['Post'])
def addUserToGroup(grpId):
    userId=getDictValue(request.json,'userId')
    
    if(userId!=""):
        grp=MemberOfGroupLW(None, grpId, userId)
        grp=MemberOfGroup.create(grp)
        return jsonify(grp.__json__()),201
    else:
        return "userId must by filled",400   
def GetGroup(grpInfo):
    users=[UserLW(x.id,x.userLogin).__json__()  for x in User.list_members_Of_Group(grpInfo.id)]
    return GroupLW(grpInfo.id,grpInfo.name, users).__json__() 
@app.route("/groups", methods=['Get'])
def getGroups():
    grps=[GetGroup(x) for x in Group.all()]
    return Response(json.dumps(grps),  mimetype='application/json')

@app.route("/users", methods=['Get'])
def getUsers():
    users=[UserLW(x.id,x.userLogin).__json__() for x in User.all()]
    return Response(json.dumps(users),  mimetype='application/json')
 

@app.route("/experiments/<expCode>/collab/bundle", methods=['Post'])
def postBundle(expCode):
    """Import Bundle of trials"""
    if experiment_in_db(expCode=expCode):
        data =  getRequestContent()
        bundle=BundleLW()
        bundle.from_json(data)
        import_bundle(bundle, expCode)
        return "",201
    
    return return_json_error_invalid_experiment_id()

@app.route("/experiments/<expCode>/collab/files", methods=['Post'])
def receiveFiles(expCode):
    """Receive zipped files"""
    
    if experiment_in_db(expCode=expCode):
        file=request.files['files']
        filedata=file.read()
        
        zF=BytesIO(filedata)
        zipObj = ZipFile(zF, 'r')
        for fName in zipObj.namelist():
            content.put(zipObj.read(fName), fName)

        zipObj.close()
        zF.close()
        return "",201
    
    return return_json_error_invalid_experiment_id()

@app.route("/downloadFile/<fid>", methods=['Get'])
@app.route("/experiments/<expCode>/downloadFile/<fid>", methods=['Get'])
@app.route("/experiments/<expCode>/collab/files/<fid>", methods=['Get'])
def downloadFile(fid, expCode=None):
    """Respond files hash"""
    resp=content.get(fid)
    return send_file(IO(resp), mimetype='application/octet-stream')

def experiment_in_db(expCode):
    return len(relational.session.query(Experiment.m).filter(Experiment.m.id == expCode).all()) == 1

@app.route("/experiments/<expCode>/collab/files", methods=['Get'])
def listFiles(expCode):
    """Respond files hash"""
    if experiment_in_db(expCode=expCode):
        resp=content.listAll()
        return jsonify(resp)
    
    return return_json_error_invalid_experiment_id()

@app.route("/experiments/<expCode>/collab/trialsids")
def trialsId(expCode):
    """Respond trials ids"""
    if experiment_in_db(expCode=expCode):
        resp=[t.id for t in Trial.list_from_experiment(expCode)]
        return jsonify(resp)
    
    return return_json_error_invalid_experiment_id()


@app.route("/experiments/<expCode>/collab/usersids")
def usersId(expCode):
    """Respond users ids"""
    if experiment_in_db(expCode=expCode):
        resp=[u.id for u in User.all()]
        return jsonify(resp)
    
    return return_json_error_invalid_experiment_id()

def return_json_error_invalid_experiment_id():
    return jsonify("Invalid experiment ID"), 400

@app.route("/experiments/<expId>/trials.json")
@app.route("/trials.json")
@app.route("/trials") # remove
def trials(expId=None):
    """Respond history graph as JSON"""
    history = History(script=request.args.get("script"),
                      status=request.args.get("execution"),
                      summarize=bool(int(request.args.get("summarize"))),
                      expId=expId)
    return jsonify(**history.graph.graph())

#generate dafalowdataflow
@app.route("/experiments/<expCode>/trials/<tid>/flow.pdf")
@app.route("/trials/<tid>/flow.pdf")
def dataflow(tid):
    """Generates the dafalow of a trial """ 
    trial = Trial(tid)
    display = DotDisplay(trial.dot.export_text(), format="pdf")
    return send_file(
        io.BytesIO(display.display_result()["application/pdf"]),
        download_name='flow.pdf',
        mimetype="application/pdf"
    )

@app.route("/experiments/<expCode>/trials/<tid>/<script_hash>/<name>") 
@app.route("/trials/<tid>/<script_hash>/<name>")    
def get_script(tid, script_hash, name):
    """Returns the executed script"""
    return send_file(
        io.BytesIO(content.get(script_hash)),
        download_name=f"{name}.py"
    )

@app.route("/experiments/<expCode>/trials/files/<file_hash>/<file_ext>")
@app.route("/trials/files/<file_hash>/<file_ext>")
def get_file(file_hash, file_ext):
    """Returns a file used in the trial"""
    name = file_hash + file_ext
    return send_file(
        io.BytesIO(content.get(file_hash)),
        download_name=name
    )
    
@app.route("/experiments/<expCode>/getFileContent/<file_hash>")
@app.route("/getFileContent/<file_hash>")
def get_file_content(file_hash, expCode=None):
    """Returns a file's content"""
    return jsonify(file_content=content.get(file_hash).decode(errors="ignore"))

@app.route("/experiments/<expCode>/trials/<tid>/<graph_mode>/<cache>.json")
@app.route("/trials/<tid>/<graph_mode>/<cache>.json")
def trial_graph(tid, graph_mode, cache,expCode=None):
    """Respond trial graph as JSON"""
    trial = Trial(tid)
    graph = trial.graph
    graph.use_cache &= bool(int(cache))
    _, tgraph, _ = getattr(graph, graph_mode)()
    return jsonify(**tgraph)

@app.route("/experiments/<expCode>/trials/<tid>/prospective.dot")
@app.route("/trials/<tid>/prospective.dot")
def prospective_provenance(tid, expCode=None):
    """Respond prospective provenance as DOT format"""
    try:
        trial = Trial(tid)
        dot_content = generate_prospective_prov(trial)
        return Response(dot_content, mimetype='text/plain')
    except ValueError as e:
        # Trial not found or not finished, return error
        error_msg = f"Error generating prospective provenance: {str(e)}"
        return Response(error_msg, status=400, mimetype='text/plain')
    except Exception as e:
        # Unexpected error
        error_msg = f"Unexpected error: {str(e)}"
        return Response(error_msg, status=500, mimetype='text/plain')

@app.route("/experiments/<expCode>/trials/<tid>/dependencies.json")
@app.route("/trials/<tid>/dependencies.json")
@app.route("/trials/<tid>/dependencies")  # remove
def dependencies(tid,expCode=None):
    """Respond trial module dependencies as JSON"""
    # pylint: disable=not-an-iterable
    trial = Trial(tid)
    result = [x.to_dict(extra=("code_hash",)) for x in trial.modules]
    trial_path = trial.path
    return jsonify(all=result, trial_path=trial_path)


@app.route("/experiments/<expCode>/trials/<tid>/environment.json")
@app.route("/trials/<tid>/environment.json")
@app.route("/trials/<tid>/environment")  # remove
def environment(tid,expCode=None):
    """Respond trial environment variables as JSON"""
    trial = Trial(tid)
    result = {x.name: x.to_dict() for x in trial.environment_attrs}
    return jsonify(all=list(result.values()))


@app.route("/experiments/<expCode>/trials/<tid>/file_accesses.json")
@app.route("/trials/<tid>/file_accesses.json")
@app.route("/trials/<tid>/file_accesses")  # remove
def file_accesses(tid,expCode=None):
    """Respond trial file accesses as JSON"""
    trial = Trial(tid)
    trial_path = trial.path
    return jsonify(file_accesses=[x.to_dict(extra=("stack",))
                                  for x in trial.file_accesses],
                   trial_path=trial_path)

@app.route("/experiments/<expCode>/trials/<tid>/activations/<aid>.json")
@app.route("/experiments/<expCode>/trials/<tid>/activations/<aid>")
@app.route("/trials/<tid>/activations/<aid>.json")
@app.route("/trials/<tid>/activations/<aid>")
def activations(tid, aid):
    """Respond trial activation as text"""
    activation = Activation((tid, aid))
    global_evaluations = activation.filter_evaluations_by_type("global")
    param_evaluations = activation.filter_evaluations_by_type("param")
    return jsonify(
        id=aid,
        line=activation.line,
        name=activation.name,
        start=activation.start,
        finish=activation.finish,
        duration=activation.duration,
        globals=["{} = {}".format(*evaluation) for evaluation in global_evaluations],
        parameters=["{} = {}".format(*evaluation) for evaluation in param_evaluations],
        return_value=activation.this_evaluation.repr,
        hash=activation.code_block.code_hash if activation.code_block is not None else "",
    )
    
@app.route("/experiments/<expCode>/diff/<trial1>/<trial2>/info.json")
@app.route("/diff/<trial1>/<trial2>/info.json")
def diff(trial1, trial2,expCode=None):
    """Respond trial diff as JSON"""
    diff_object = Diff(trial1, trial2)
    return jsonify(
        trial1=diff_object.trial1.to_dict(extra=("duration_text",)),
        trial2=diff_object.trial2.to_dict(extra=("duration_text",)),
        trial=diff_object.trial,
    )

@app.route("/experiments/<expCode>/diff/<trial1>/<trial2>/dependencies.json")
@app.route("/diff/<trial1>/<trial2>/dependencies.json")
def diff_modules(trial1, trial2,expCode=None):
    """Respond modules diff as JSON"""
    diff_object = Diff(trial1, trial2)
    modules_added, modules_removed, modules_replaced = diff_object.modules
    t1_path = diff_object.trial1.path
    t2_path = diff_object.trial2.path
    return jsonify(
        modules_added=[x.to_dict(extra=("code_hash",)) for x in modules_added],
        modules_removed=[x.to_dict(extra=("code_hash",)) for x in modules_removed],
        modules_replaced=[[y.to_dict(extra=("code_hash",)) for y in x] for x in modules_replaced],
        t1_path=t1_path,
        t2_path=t2_path,
    )

@app.route("/experiments/<expCode>/diff/<trial1>/<trial2>/environment.json")
@app.route("/diff/<trial1>/<trial2>/environment.json")
def diff_environment(trial1, trial2,expCode=None):
    """Respond environment diff as JSON"""
    diff_object = Diff(trial1, trial2)
    env_added, env_removed, env_replaced = diff_object.environment
    return jsonify(
        env_added=[x.to_dict() for x in env_added],
        env_removed=[x.to_dict() for x in env_removed],
        env_replaced=[[y.to_dict() for y in x] for x in env_replaced],
    )

@app.route("/experiments/<expCode>/diff/<trial1>/<trial2>/file_accesses.json")
@app.route("/diff/<trial1>/<trial2>/file_accesses.json")
def diff_accesses(trial1, trial2,expCode=None):
    """Respond trial diff as JSON"""
    diff_object = Diff(trial1, trial2)
    fa_added, fa_removed, fa_replaced = diff_object.file_accesses
    t1_path = diff_object.trial1.path
    t2_path = diff_object.trial2.path
    return jsonify(
        fa_added=[x.to_dict() for x in fa_added],
        fa_removed=[x.to_dict() for x in fa_removed],
        fa_replaced=[[y.to_dict() for y in x] for x in fa_replaced],
        t1_path=t1_path,
        t2_path=t2_path,
    )

@app.route("/experiments/<expCode>/diff/<trial1>/<trial2>/<graph_mode>-<cache>.json")
@app.route("/diff/<trial1>/<trial2>/<graph_mode>-<cache>.json")
def diff_graph(trial1, trial2, graph_mode, cache,expCode=None):
    """Respond trial diff as JSON"""
    diff_object = Diff(trial1, trial2)
    graph = diff_object.graph
    graph.use_cache &= bool(int(cache))

    _, diff_result, _ = getattr(graph, graph_mode)()
    return jsonify(**diff_result)

@app.route("/definition/<trial_id>/ast.json")
def definition_ast(trial_id):
    """Respond trial definition as AST"""
    trial = Trial(trial_id)
    ast = TrialAst(trial)
    return jsonify(ast.construct_ast_json(False))

@app.route("/experiments/<expCode>/getAllTrialsIdsAndTags")
@app.route("/getAllTrialsIdsAndTags")
def get_all_trials_ids_and_tags():
    return jsonify([{"id": trial.id, "tag": list(trial.tags)[0].name} for trial in Trial.all()])

@app.route("/experiments/<expCode>/getFunctionActivations/<trial_id>")
@app.route("/getFunctionActivations/<trial_id>")
def get_function_activations_from_trial(trial_id):
    function_activations = relational.session.query(Activation.m).filter(Activation.m.trial_id == trial_id).all()
    function_activations_array = []
    for activation in function_activations:
        activation_dict = {"id": activation.id, "name": activation.name}
        activation_dict["params"] = get_function_activation_arguments(trial_id, activation.id).json["function_params"]
        if("This function has no params" in activation_dict["params"]): activation_dict["params"] = ""
        function_activations_array.append(activation_dict)
    return jsonify(function_activations=function_activations_array)

@app.route("/experiments/<expCode>/diff/getFunctionActivationArguments/<trial_id>/<function_id>")
@app.route("/diff/getFunctionActivationArguments/<trial_id>/<function_id>")
def get_function_activation_arguments(trial_id, function_id, expCode=None):
    function_arguments = relational.session.query(Dependency.m).filter(Dependency.m.trial_id==trial_id, Dependency.m.dependent_id==int(function_id), Dependency.m.type=="argument").all()
    if len(function_arguments) < 1: return jsonify(function_params="This function has no params")
    
    function_params = [relational.session.query(Evaluation.m).filter(Evaluation.m.id==argument.dependency_id, Evaluation.m.trial_id==trial_id).all()[0].repr for argument in function_arguments]
    return jsonify(function_params=function_params)

@app.route("/experiments/<expCode>/commands/diff/<trial1_id>/<activation1_id>/<trial2_id>/<activation2_id>")
@app.route("/commands/diff/<trial1_id>/<activation1_id>/<trial2_id>/<activation2_id>")
def execute_command_diff_function_activation(trial1_id, activation1_id, trial2_id, activation2_id, expCode=None):
    diff = Diff(trial1_id, trial2_id)
    diffCMD = DiffCMD()
    
    functions_info = diffCMD.get_diff_function_info(trial1_id, trial2_id, activation1_id, activation2_id, diff.file_accesses, "all")    
    differ = difflib.Differ()
    trial1_variables_that_changed, trial2_variables_added, trial1_variables_removed = diffCMD.build_variables_lcs(functions_info["variables_function_trial1"], functions_info["variables_function_trial2"], differ)
    
    functions_info["file_accesses_added"] = list([{"name": obj.name, "mode": obj.mode , "buffering": obj.buffering, "content_hash_before": obj.content_hash_before, "content_hash_after": obj.content_hash_after, "timestamp": obj.timestamp, "stack": obj.stack} for obj in functions_info["file_accesses_added"]])
    functions_info["file_accesses_removed"] = list([{"name": obj.name, "mode": obj.mode , "buffering": obj.buffering, "content_hash_before": obj.content_hash_before, "content_hash_after": obj.content_hash_after, "timestamp": obj.timestamp, "stack": obj.stack} for obj in functions_info["file_accesses_removed"]])
    functions_info["file_accesses_replaced"] = list([{"name": obj[0].name, "content_hash_before_first_trial": obj[0].content_hash_before, "content_hash_before_second_trial": obj[1].content_hash_before, "content_hash_after_first_trial": obj[0].content_hash_after, "content_hash_after_second_trial": obj[1].content_hash_after, "timestamp_first_trial": obj[0].timestamp, "timestamp_second_trial": obj[1].timestamp, "checkpoint_first_trial": obj[0].checkpoint, "checkpoint_second_trial": obj[1].checkpoint} for obj in functions_info["file_accesses_replaced"]])
    
    functions_info["trial1_variables_that_changed"] = [('\n'.join(list(diff_var))) for diff_var in trial1_variables_that_changed]
    functions_info["trial2_variables_added"] = [(str(var)+"\n") for var in trial2_variables_added]
    functions_info["trial1_variables_removed"] = [(str(var)+"\n") for var in trial1_variables_removed]

    return jsonify(functions_info), 200

@app.route("/commands/restore/trial/<trial_id>/<skip_script>/<skip_modules>/<skip_files_access>")
def execute_command_restore_trial(trial_id, skip_script, skip_modules, skip_files_access):
    """Execute the command 'now restore' for a trial"""
    restore_command = ("now restore " + trial_id).split()
    if skip_script == "true": restore_command.append("-s")
    if skip_modules == "true": restore_command.append("-l")
    if skip_files_access == "true": restore_command.append("-a")
    
    sub_proccess_print = subprocess.run(restore_command, capture_output=True).stdout.decode("utf-8")
    # os.system(restore_command)
    return jsonify(terminal_text=sub_proccess_print), 200

@app.route("/commands/restore/file/<trial_id>/<file_to_restore>/<file_id>/<path:output_path>")
def execute_command_restore_file(trial_id, file_to_restore, file_id, output_path):
    """Execute the command 'now restore' for a file"""
    restore_command = ("now restore " + trial_id + " -f").split()
    restore_command.append(file_to_restore)
    if file_id != "false": 
        restore_command.append("-i")
        restore_command.append(file_id)
    if output_path != "false":
        restore_command.append("-t")
        restore_command.append(output_path)
    
    sub_process = subprocess.run(restore_command, capture_output=True)
    
    erro_string = sub_process.stderr.decode("utf-8")    
    if (len(erro_string) > 0): return jsonify(terminal_text="\""+ output_path +"\" No such file or directory"), 400

    sub_proccess_print = sub_process.stdout.decode("utf-8")
    status = 400 if ("Unable" in sub_proccess_print) or ("not" in sub_proccess_print) else 200
    return jsonify(terminal_text=sub_proccess_print), status

@app.route("/commands/prov/<trial_id>")
def execute_command_prov(trial_id):
    """Execute the command 'now prov'"""
    prov_command = ("now prov " + trial_id).split()
    sub_process_print = subprocess.run(prov_command, capture_output=True).stdout.decode("utf-8")
    if "(" in sub_process_print: return jsonify(prov=sub_process_print), 200
    return jsonify(prov="No prov to export"), 400
    
@app.route("/commands/export/<trial_id>/<rules>/<hide_timestamps>")
def execute_command_export(trial_id, rules, hide_timestamps):
    """Execute the command 'now export'"""
    export_command = ("now export " + trial_id).split()
    
    if rules == "true": export_command.append("-r")
    if hide_timestamps == "true": export_command.append("-t")
    
    sub_process_print = subprocess.run(export_command, capture_output=True).stdout.decode("utf-8")
    return jsonify(export=sub_process_print), 200

@app.route("/commands/dataflow/<trial_id>/<argument_T>/<argument_t>/<argument_H>/<argument_hnc>/<argument_an>/<argument_hf>/<file_accesses>/<evaluation>/<group>/<depth>/<value_length>/<name>/<mode>/<wdf>/<eid>")
def execute_dataflow_export(trial_id, argument_T, argument_t, argument_H, argument_hnc, argument_an, argument_hf,file_accesses, evaluation, group, depth, value_length, name, mode, wdf, eid):
    """Execute the command 'now export'"""
    dataflow_command = ("now dataflow " + trial_id).split()
    
    if argument_T == "true": dataflow_command.append("-T")
    if argument_t == "true": dataflow_command.append("-t")
    if argument_H == "true": dataflow_command.append("-H")
    if argument_hnc == "true": dataflow_command.append("-hnc")
    if argument_an == "true": dataflow_command.append("-an")
    if argument_hf == "true": dataflow_command.append("-hf")
    if wdf == "true":
        dataflow_command.append("-w")
        dataflow_command.append(eid)
    
    appendDataflowCommandWithParameters(dataflow_command, "-a", file_accesses, 0, 4, 1)
    appendDataflowCommandWithParameters(dataflow_command, "-e", evaluation, 0, 2, 1)
    appendDataflowCommandWithParameters(dataflow_command, "-g", group, 0, 2, 0)
    appendDataflowCommandWithParameters(dataflow_command, "-d", depth, 0, float('inf'), 0)
    appendDataflowCommandWithParameters(dataflow_command, "--value-length", value_length, 0, float('inf'), 0)
    appendDataflowCommandWithParameters(dataflow_command, "-n", name, 0, float('inf'), 55)

    dataflow_command.append("-m")
    if mode in ["activation", "coarseGrain", "looplessCoarseGrain", "fineGrain", "all"]: dataflow_command.append(mode)
    else: dataflow_command.append("prospective")
    
    sub_process_print = subprocess.run(dataflow_command, capture_output=True).stdout.decode("utf-8")
    return jsonify(dataflow=sub_process_print), 200

def appendDataflowCommandWithParameters(export_command, command, parameter_value, min_value, max_value, default_value):
    export_command.append(command)
    if int(parameter_value) > max_value or int(parameter_value) < min_value: export_command.append(str(default_value))
    else: export_command.append(str(parameter_value))

@app.route("/dataflow/evaluations/<trial_id>")
def get_evaluations_from_trial(trial_id):
    from sqlalchemy import or_
    evaluations_query = relational.session.query(Evaluation.m.id, CodeComponent.m.name, CodeComponent.m.first_char_line).filter(
            Evaluation.m.trial_id==trial_id, 
            Evaluation.m.code_component_id == CodeComponent.m.id, 
            CodeComponent.m.trial_id == trial_id).all()
    return jsonify(evaluations=[{"evaluation_id": x[0], "name": x[1], "first_char_line": x[2]} for x in evaluations_query]), 200
    
@app.route("/collab/remotes/getall")
def get_all_remotes():
    return jsonify(remotes=[RemoteLW(x.id, x.server_url, x.name, x.used, x.hide).__json__() for x in Remote.all() if x.hide == False]), 200

@app.route("/collab/remotes/add/<remote_name>/<path:remote_url>", methods=['Post'])
def add_remote(remote_name, remote_url):
    Remote.create(remote_url, remote_name)
    return jsonify(terminal_text="Remote " + remote_name + " added successfully"), 200

@app.route("/collab/remotes/edit/<remote_new_name>/<path:remote_url>")
def edit_remote(remote_new_name, remote_url):
    remote_url_list = relational.session.query(Remote.m).filter(Remote.m.server_url == remote_url).all()
    if(len(remote_url) <= 0): return jsonify(text="Remote url " + remote_url  + " not found"), 400
    remote = remote_url_list[0]
    remote.name = remote_new_name
    relational.session.commit()
    return jsonify(terminal_text="Remote "+ remote_url + " name changed successfully to " + remote_new_name), 200

@app.route("/collab/remotes/delete/<path:remote_url>")
def delete_remote(remote_url):
    remote_url_list = relational.session.query(Remote.m).filter(Remote.m.server_url == remote_url).all()
    if(len(remote_url) <= 0): return jsonify(text="Remote url " + remote_url  + " not found"), 400
    remote = remote_url_list[0]
    if remote.used: remote.hide = True
    else: relational.session.delete(remote)
    relational.session.commit()
    return jsonify(terminal_text="Remote "+ remote_url + " deleted successfully"), 200

@app.route("/commands/<collab_command>/<path:serverUrl>")
def execute_command_push_experiment(collab_command, serverUrl):
    """Execute the command 'now push'"""
    push_command = ("now " + collab_command + " --url " + serverUrl).split()
    
    sub_process = subprocess.run(push_command, capture_output=True)
    if(len(sub_process.stderr)): return jsonify(terminal_text="Invalid server address"), 400
    
    sub_process_print = sub_process.stdout.decode("utf-8")
    status_code = 200
    if return_json_error_invalid_experiment_id()[0].json in sub_process_print: status_code = 400       
    
    return jsonify(terminal_text=sub_process_print), status_code

@app.route("/files/<trial_id>")
def get_files_belonging_to_trial(trial_id):   
    files = []
    for file in FileAccess.all():
        if file.trial_id  == trial_id and file.name != "nul": files.append(file.name)
    for trial in Trial.all():
        if trial.id == trial_id: files.append(trial.script)
    for module in Module.all():
        if module.trial_id == trial_id:
            module_path = module.path
            if "/" in module_path: files.append(module_path.split("/")[-1])
            elif "\\" in module_path: files.append(module_path.split("\\")[-1])
            # files.append(module.path.split(os.sep)[-1])
        
    return jsonify(files=files), 200

@app.teardown_appcontext
def shutdown_session(exception=None):
    """Shutdown SQLAlchemy session"""
    # pylint: disable=unused-argument
    relational.session.remove()

@app.route("/db/tables")
def db_tables():
    conn = relational.engine.raw_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
        tables = [row[0] for row in cursor.fetchall()]
        
        foreign_keys = {}
        for table in tables:
            cursor.execute(f"PRAGMA foreign_key_list('{table}')")
            table_fks = []
            for fk in cursor.fetchall():
                table_fks.append({
                    "id": fk[0],
                    "seq": fk[1],
                    "table": fk[2],
                    "from": fk[3],
                    "to": fk[4],
                    "on_update": fk[5],
                    "on_delete": fk[6],
                    "match": fk[7]
                })
            if table_fks:
                foreign_keys[table] = table_fks
        
        return jsonify({
            "tables": tables,
            "foreign_keys": foreign_keys
        })
    finally:
        conn.close()

@app.route("/db/table/<table_name>")
def db_table_info(table_name):
    conn = relational.engine.raw_connection()
    try:
        cursor = conn.cursor()
        
        cursor.execute(f"PRAGMA table_info('{table_name}')")
        columns = []
        for col in cursor.fetchall():
            columns.append({
                "name": col[1],
                "type": col[2],
                "notnull": bool(col[3]),
                "default": col[4],
                "pk": bool(col[5]),
            })
        
        cursor.execute(f"PRAGMA foreign_key_list('{table_name}')")
        foreign_keys = []
        for fk in cursor.fetchall():
            foreign_keys.append({
                "id": fk[0],
                "seq": fk[1],
                "table": fk[2],
                "from": fk[3],
                "to": fk[4],
                "on_update": fk[5],
                "on_delete": fk[6],
                "match": fk[7]
            })
        
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        all_tables = [row[0] for row in cursor.fetchall()]
        
        referenced_by = []
        for table in [t for t in all_tables if t != table_name]:
            cursor.execute(f"PRAGMA foreign_key_list('{table}')")
            for fk in [fk for fk in cursor.fetchall() if fk[2] == table_name]:
                referenced_by.append({
                    "referencing_table": table,
                    "referencing_column": fk[3],
                    "referenced_column": fk[4],
                    "on_update": fk[5],
                    "on_delete": fk[6]
                })

        return jsonify({
            "columns": columns,
            "foreign_keys": foreign_keys,
            "referenced_by": referenced_by
        })
    except Exception as e:
        return jsonify({"error": str(e)})
    finally:
        conn.close()

@app.route("/db/query", methods=["POST"])
def db_query():
    data = request.get_json()
    query = data.get("query", "")
    if not query.strip():
        return jsonify({"error": "No query provided"}), 400
    
    transaction_keywords = ['BEGIN', 'COMMIT', 'ROLLBACK', 'SAVEPOINT', 'RELEASE', 'TRANSACTION']
    query_upper = query.upper()
    for keyword in transaction_keywords:
        if keyword in query_upper:
            return jsonify({"error": f"Query contains dangeroous keyword '{keyword}' which is not allowed"}), 400
    
    conn = None
    cursor = None
    try:
        conn = relational.engine.raw_connection()
        cursor = conn.cursor()
        
        cursor.execute("BEGIN TRANSACTION")
        
        cursor.execute(query)
        if cursor.description:
            columns = [desc[0] for desc in cursor.description]
            rows = [dict(zip(columns, row)) for row in cursor.fetchall()]
            result = {"columns": columns, "rows": rows}
        else:
            result = {"columns": [], "rows": []}
        
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)})
    finally:
        if cursor:
            cursor.execute("ROLLBACK") # Always rollback 

        if conn:
            conn.close()