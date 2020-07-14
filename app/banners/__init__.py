from flask import Blueprint

banners = Blueprint('banners', __name__)

from . import banner_api
