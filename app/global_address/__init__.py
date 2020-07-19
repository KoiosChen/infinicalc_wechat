from flask import Blueprint

global_address = Blueprint('global_address', __name__)

from . import countries
