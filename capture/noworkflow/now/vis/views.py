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

from flask import render_template, jsonify, request, make_response, send_file,send_file, Response
from io import BytesIO as IO

from ..persistence.models import Trial, Activation,Activation, Experiment, ExtendedAnnotation, Group, User, MemberOfGroup
from ..persistence.lightweight import ActivationLW, BundleLW, ExperimentLW, ExtendedAnnotationLW,GroupLW,UserLW,MemberOfGroupLW
from ..models.history import History
from ..models.diff import Diff
from ..persistence import relational, content
from ..ipython.dotmagic import DotDisplay

import subprocess
from ..utils.collab import export_bundle, import_bundle
from ..utils.compression import gzip_compress,gzip_uncompress
from ..persistence import content
import time
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
    trialsToExport=request.args.getlist("id")
    bundle=export_bundle(trialsToExport)
    resp=bundle.__json__()
    return jsonify(resp)

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
    return send_file(IO(bytes(annt.annotation, 'utf-8')),mimetype='application/octet-stream',as_attachment=True,attachment_filename=id+"."+extention)


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
    data =  getRequestContent()
    bundle=BundleLW()
    bundle.from_json(data)
    import_bundle(bundle, expCode)
    return "",201

@app.route("/experiments/<expCode>/collab/files", methods=['Post'])
def receiveFiles(expCode):
    """Receive zipped files"""

    file=request.files['files']
    filedata=file.read()
    
    zF=BytesIO(filedata)
    zipObj = ZipFile(zF, 'r')
    for fName in zipObj.namelist():
        content.put(zipObj.read(fName), fName)

    zipObj.close()
    zF.close()
    return "",201

@app.route("/experiments/<expCode>/collab/files/<fid>", methods=['Get'])
def downloadFile(expCode,fid):
    """Respond files hash"""
    resp=content.get(fid)
    return send_file(IO(resp),mimetype='application/octet-stream')

@app.route("/experiments/<expCode>/collab/files", methods=['Get'])
def listFiles(expCode):
    """Respond files hash"""
    resp=content.listAll()
    return jsonify(resp)

@app.route("/experiments/<expCode>/collab/trialsids")
def trialsId(expCode):
    """Respond trials ids"""
    resp=[t.id for t in Trial.list_from_experiment(expCode)]
    return jsonify(resp)
@app.route("/experiments/<expCode>/collab/usersids")
def usersId(expCode):
    """Respond users ids"""
    resp=[u.id for u in User.all()]
    return jsonify(resp)

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
        attachment_filename='flow.pdf',
        mimetype="application/pdf"
    )

@app.route("/experiments/<expCode>/trials/<tid>/<script_hash>/<name>") 
@app.route("/trials/<tid>/<script_hash>/<name>")    
def get_script(tid, script_hash, name):
    """Returns the executed script"""
    return send_file(
        io.BytesIO(content.get(script_hash)),
        attachment_filename=name + '.py'
    )

@app.route("/experiments/<expCode>/trials/files/<file_hash>/<file_ext>")
@app.route("/trials/files/<file_hash>/<file_ext>")
def get_file(file_hash, file_ext):
    """Returns a file used in the trial"""
    name = file_hash + file_ext
    return send_file(
        io.BytesIO(content.get(file_hash)),
        attachment_filename=name
    )

@app.route("/experiments/<expCode>/trials/<tid>/<graph_mode>/<cache>.json")
@app.route("/trials/<tid>/<graph_mode>/<cache>.json")
def trial_graph(tid, graph_mode, cache,expCode=None):
    """Respond trial graph as JSON"""
    trial = Trial(tid)
    graph = trial.graph
    graph.use_cache &= bool(int(cache))
    _, tgraph, _ = getattr(graph, graph_mode)()
    return jsonify(**tgraph)

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
    if ("No such file or directory" in erro_string): return jsonify(terminal_text="\""+ output_path +"\" No such file or directory"), 400
    
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
    
@app.route("/commands/export/<trial_id>")
def execute_command_export(trial_id):
    """Execute the command 'now export'"""
    export_command = ("now export " + trial_id).split()
    sub_process_print = subprocess.run(export_command, capture_output=True).stdout.decode("utf-8")
    return jsonify(export=sub_process_print), 200

@app.route("/commands/dataflow/<trial_id>/<argument_T>/<argument_t>/<argument_H>/<file_accesses>/<evaluation>/<group>/<depth>/<value_length>/<name>/<mode>")
def execute_dataflow_export(trial_id, argument_T, argument_t, argument_H, file_accesses, evaluation, group, depth, value_length, name, mode):
    """Execute the command 'now export'"""
    export_command = ("now dataflow " + trial_id).split()
    
    if argument_T == "true": export_command.append("-T")
    if argument_t == "true": export_command.append("-t")
    if argument_H == "true": export_command.append("-H")
    
    appendDataflowCommandWithParameters(export_command, "-a", file_accesses, 0, 4, 1)
    appendDataflowCommandWithParameters(export_command, "-e", evaluation, 0, 2, 1)
    appendDataflowCommandWithParameters(export_command, "-g", group, 0, 2, 0)
    appendDataflowCommandWithParameters(export_command, "-d", depth, 0, float('inf'), 0)
    appendDataflowCommandWithParameters(export_command, "--value-length", value_length, 0, float('inf'), 0)
    appendDataflowCommandWithParameters(export_command, "-n", name, 0, float('inf'), 55)

    export_command.append("-m")
    if mode in ["simulation", "activation" , "dependency"]: export_command.append(mode)
    else: export_command.append("prospective")
    
    print(export_command)
    
    sub_process_print = subprocess.run(export_command, capture_output=True).stdout.decode("utf-8")
    return jsonify(dataflow=sub_process_print), 200

def appendDataflowCommandWithParameters(export_command, command, parameter_value, min_value, max_value, default_value):
    export_command.append(command)
    if int(parameter_value) > max_value or int(parameter_value) < min_value: export_command.append(str(default_value))
    else: export_command.append(str(parameter_value))

@app.route("/commands/<collab_command>/<expCode>/<path:serverUrl>")
def execute_command_push_experiment(collab_command, expCode, serverUrl):
    """Execute the command 'now push'"""
    push_command = ("now " + collab_command + " --url " + serverUrl + "/experiments/" + expCode).split()
    
    sub_process = subprocess.run(push_command, capture_output=True)
    
    if(len(sub_process.stderr)): return jsonify(terminal_text="Invalid server address"), 400
    
    return jsonify(terminal_text=sub_process.stdout.decode("utf-8")), 200

@app.teardown_appcontext
def shutdown_session(exception=None):
    """Shutdown SQLAlchemy session"""
    # pylint: disable=unused-argument
    relational.session.remove()
