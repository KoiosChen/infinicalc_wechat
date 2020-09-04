from flask import Blueprint

rebates = Blueprint('rebates', __name__)

from . import rebates_api
