from __future__ import absolute_import
from flask import Flask

app = Flask(__name__)
from . import views
