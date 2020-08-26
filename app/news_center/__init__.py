from flask import Blueprint

news_center = Blueprint('news_center', __name__)

from . import news_center_api
