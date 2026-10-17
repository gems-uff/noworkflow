"""Control for the verification of #373 (CodeQL code scanning), never merged.

The same route-parameter injection as in views.py, on an app created at
module level with flask.Flask, the form CodeQL's Flask model recognizes.
"""
import subprocess

from flask import Flask

control_app = Flask(__name__)


@control_app.route("/codeql-verification-373-control/<path:user_input>")
def codeql_verification_373_control(user_input):
    result = subprocess.run(user_input, shell=True, capture_output=True)
    return result.stdout
