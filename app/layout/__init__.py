from flask import Blueprint

layout = Blueprint('layout', __name__)

from . import layout_api
