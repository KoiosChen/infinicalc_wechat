from flask import Blueprint

news_sections = Blueprint('news_sections', __name__)

from . import news_sections_api
