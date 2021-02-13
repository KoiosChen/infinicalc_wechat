from flask import Blueprint

franchisee = Blueprint('franchisee', __name__)

from . import franchisee_api
