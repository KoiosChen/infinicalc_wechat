from flask import Blueprint

invitation_code = Blueprint('invitation_code', __name__)

from . import invitation_api
