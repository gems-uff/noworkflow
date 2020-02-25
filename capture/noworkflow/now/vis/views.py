# Copyright (c) 2016 Universidade Federal Fluminense (UFF)
# Copyright (c) 2016 Polytechnic Institute of New York University.
# This file is part of noWorkflow.
# Please, consult the license terms in the LICENSE file.
"""Define views for 'now vis'"""
from __future__ import (absolute_import, print_function,
                        division, unicode_literals)

import os
import json

from flask import render_template, jsonify, request,send_file  
from io import BytesIO as IO

from ..persistence.models import Trial,Activation, Experiment
from ..persistence.lightweight import ActivationLW, BundleLW, ExperimentLW
from ..models.history import History
from ..models.diff import Diff
from ..persistence import relational
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
    if expcode is None:
        expcode=""
    history = History()
    return render_template(
        "index.html",
        cwd=os.getcwd(),
        scripts=history.scripts,
        experiments=experiments,
        selectedExperiment=expcode
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
        content.put(zipObj.read(fName))

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


@app.teardown_appcontext
def shutdown_session(exception=None):
    """Shutdown SQLAlchemy session"""
    # pylint: disable=unused-argument
    relational.session.remove()
