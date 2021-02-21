from flask import Blueprint

items_verification = Blueprint('items_verification', __name__)

from . import items_verification_api
