from flask import Blueprint

promotion_groups = Blueprint('promotion_groups', __name__)

from . import promotion_groups_api
