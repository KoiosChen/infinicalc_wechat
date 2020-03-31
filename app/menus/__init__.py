from flask import Blueprint

menus = Blueprint('menus', __name__)

from . import menus_api
