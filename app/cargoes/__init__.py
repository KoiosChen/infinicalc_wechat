from flask import Blueprint

cargoes = Blueprint('cargoes', __name__)

from . import total_cargoes
