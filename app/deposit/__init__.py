from flask import Blueprint

deposit = Blueprint('deposit', __name__)

from . import deposit_api
