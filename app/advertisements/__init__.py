from flask import Blueprint

advertisements = Blueprint('advertisements', __name__)

from . import advertisements_api
